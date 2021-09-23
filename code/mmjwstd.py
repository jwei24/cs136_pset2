#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class MMJWStd(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.optunchoked = 0
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces)))))
        np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            isect_list = list(isect)
            random.shuffle(isect_list)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            piece_count={}
            for piece_id in isect_list:
                if piece_id in piece_count:
                    piece_count[piece_id]+= 1
                else:
                    piece_count[piece_id]=1
            rarest_first=sorted(piece_count.items(), key=lambda x:x[1])
            for piece_id, counts in rarest_first:
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.
        chosen=[]

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"
            if round == 0 or round == 1:
                rids = random.sample(requests, min(3, len(requests)))
                chosen = [x.requester_id for x in rids]
            else:
                requester_id_list = list(set(request.requester_id for request in requests))
                requester_id_dict = {id: 0 for id in requester_id_list}
                for i in range(round-2, round):
                    for download in history.downloads[i]:
                        pid = download.from_id
                        blockrate = download.blocks
                        if pid in requester_id_dict:
                            requester_id_dict[pid] += blockrate

                rid_dict_sorted = sorted(requester_id_dict.items(), key=lambda x:x[1], reverse=True)
                for pid, blockrate in rid_dict_sorted:
                    if len(chosen) == 3 or blockrate == 0:
                        exit
                    if pid in requester_id_list:
                        chosen.append(pid)
                        requester_id_list.remove(pid)
                    else:
                        continue
                if len(chosen) == 0:
                    rids = random.sample(requester_id_list, min(3, len(requester_id_list)))
                    chosen = [x for x in rids]
                if round%3==0 and len(requester_id_list) > 0:
                    opt = random.sample(requester_id_list, 1)
                    chosen.append(opt)
                    self.optunchoked=opt
                else:
                    chosen.append(self.optunchoked)
            # Evenly "split" my upload bandwidth among the one chosen requester
            bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
