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

class MMJWTyrant(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.gamma = .1
        self.r = 3
        self.alpha = .2
        self.d = {}
        self.u = {}
        self.init_u = self.up_bw/4
        self.init_d = self.up_bw/4
        self.record = {}
    
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


        # Initialize record about peers
        if round == 0:
            for peer in peers:
                self.record[peer.id] = 0
                self.u[peer.id] = self.init_u
                self.d[peer.id] = self.init_d
        else:
            new_record = {}
            for download in history.downloads[round-1]:
                pid = download.from_id
                self.d[pid] = download.blocks
                if pid in self.record:
                    current = self.record[pid]
                    if current == 0:
                        new_record[pid] = 1
                    elif current < self.r:
                        new_record[pid] = self.record[pid] + 1
                    elif current == self.r:
                        new_record[pid] = self.r
                        self.u[pid] = self.u[pid]*(1-self.gamma)
            for peer in peers:
                if peer.id in new_record == False:
                    new_record[peer.id] = 0
                    self.u[peer.id] = self.u[peer.id]*(1+self.alpha)
            self.record = new_record
        
        chosen = []
        bws = []
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")

        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"
            # Check who unchoked me in the previous round
            requester_id_list = list(set(request.requester_id for request in requests))
            random.shuffle(requester_id_list)
            requester_rank = {}
            for rid in requester_id_list:
                requester_rank[rid] = self.d[rid]/self.u[rid]
            requester_rank= sorted(requester_rank.items(), key=lambda x:x[1], reverse=True)
            # Evenly "split" my upload bandwidth among the one chosen requester
            bw_left = self.up_bw
            k=0
            while bw_left > 0 and len(requester_rank) > k:
                chosen_id, rate = requester_rank[k]
                chosen.append(chosen_id)
                if bw_left - self.u[chosen_id] >= 0:
                    bws.append(self.u[chosen_id])
                    bw_left = bw_left - self.u[chosen_id]
                k+=1
                
        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
