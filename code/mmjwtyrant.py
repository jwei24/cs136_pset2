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
        self.init_u = self.up_bw/3
        self.init_d = self.up_bw/3
        self.record = {}
        self.allrequest=[]
    
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
        piece_count={}
        for peer in peers:
            for piece_id in peer.available_pieces:
                if piece_id in piece_count.keys():
                    piece_count[piece_id]+= 1
                else:
                    piece_count[piece_id]=1
        
        for peer in peers:
            i=0
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            isect_list = list(isect)
            random.shuffle(isect_list)
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            rarest_first=sorted(isect_list, key=lambda x: piece_count[x])
            for piece_id in rarest_first:
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                if piece_id in peer.available_pieces:
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
                    i+=1
                    if i >= self.max_requests:
                        break
                else:
                    continue
        # Remember what I requested
        self.allrequest.append(requests)
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
                logging.info(str(self.record))
        else:
            newrecord={}
            newd={}

            # Update records from previous round
            for download in history.downloads[round-1]:
                pid = download.from_id
                # NewD keeps track of the new values of d_{j}
                if pid in newd:
                    newd[pid] += download.blocks
                else:
                    newd[pid] = download.blocks
                # If you haven't already been updated
                if not pid in newrecord:
                    # You haven't unchoked me for the past r rounds
                    if self.record[pid] < self.r:
                        newrecord[pid] = self.record[pid] + 1
                    # You have unchoked me for the past r rounds, so I cheese you
                    else:
                        newrecord[pid] = self.r
                        self.u[pid] *= (1-self.gamma)

            
            # Updating all the people who did not unchoke me last round
            for request in self.allrequest[round - 1]:
                if not request.peer_id in newrecord:
                    newrecord[request.peer_id] = 0
                    # Give them more carrots
                    self.u[request.peer_id] *= (1+self.alpha)
                    
            # Estimating values for people who did not unchoke me
            for peer in peers:
                if not peer.id in newd:
                    tempd = len(peer.available_pieces)*self.conf.blocks_per_piece/round/4
                    if tempd != 0:
                        self.d[peer.id]
                        
            # Updating my records
            for pid in newrecord:
                self.record[pid] = newrecord[pid]
            for pid in newd:
                self.d[pid] = newd[pid]
        
        chosen = []
        bws = []
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")

        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            # Get list of IDs of people who are requesting pieces from me
            requester_id_list = list(set(request.requester_id for request in requests))
            random.shuffle(requester_id_list)
            requester_rank = {}
            # Calculate ratios
            for rid in requester_id_list:
                requester_rank[rid] = self.d[rid]/self.u[rid]
            # Rank requester by highest to lowest ratio
            requester_rank= sorted(requester_rank.items(), key=lambda x:x[1], reverse=True)

            # Allocate upload bandwidth
            bw_left = self.up_bw
            while bw_left > 0 and len(requester_rank) > 0:
                chosen_id, rate = requester_rank[0]
                chosen.append(chosen_id)
                requester_rank.pop(0)
                if bw_left - self.u[chosen_id] >= 1:
                    bws.append(self.u[chosen_id])
                    bw_left -= self.u[chosen_id]
                else:
                    bws.append(bw_left-1)
                    bw_left = 0

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
