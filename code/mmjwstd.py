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

        # Constants
        self.NUM_SLOTS = 4
        self.LOOKBACK_CNT = 2
        self.NO_UNCHOKED = -1 # ID's should be strings so this hopefully works

        # Unchoking
        self.optunchoked = self.NO_UNCHOKED
        self.choke_turn_cntr = 0
    
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
        piece_counts = {}
        for peer in peers:
            for piece_id in peer.available_pieces:
                if not piece_id in piece_counts:
                    piece_counts[piece_id] = 0
                piece_counts[piece_id] += 1
        rarest_first = list(piece_counts.items())[:]
        random.shuffle(rarest_first)
        rarest_first = sorted(rarest_first, key = lambda x: x[1])
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))

            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            cur_len = 0
            cur_rarest = list(isect)
            random.shuffle(cur_rarest)
            cur_rarest.sort(key = lambda x: piece_counts[x])
            for piece_id in cur_rarest:
                if cur_len >= self.max_requests:
                    break
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)
                cur_len += 1

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round_num = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round_num))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.
        chosen=[]

        ###################
        # Specs for std:
        # - Every time period, unchoke 3 peers from which it has recently
        #   achieved the highest bandwidth
        # - Every 3 time periods, optimistically unchoke another, random peer
        #   from the neighborhood, and leave this peer unchocked for three
        #   time periods
        ###################

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"
            
            cur_req_ids = list(set(map(lambda x: x.requester_id, requests)))
            prev_rnd_bw = dict(zip(cur_req_ids, [0] * len(cur_req_ids)))

            for i in range(max(0, round_num - self.LOOKBACK_CNT), round_num):
                for dl_obj in history.downloads[i]:
                    if not dl_obj.from_id in prev_rnd_bw:
                        continue
                    prev_rnd_bw[dl_obj.from_id] += dl_obj.blocks
            candidates = list(prev_rnd_bw.items())
            random.shuffle(candidates)
            candidates.sort(key = lambda x: x[1], reverse=True)

            unchoked_requesting = False
            if self.optunchoked != self.NO_UNCHOKED and\
                    self.optunchoked in prev_rnd_bw:
                unchoked_requesting = True
                candidates.remove((self.optunchoked,\
                                    prev_rnd_bw[self.optunchoked]))
            ## Take top NUM_SLOTS - 1, leave last for unchoking.
            if len(candidates) <= self.NUM_SLOTS - 1:
                chosen, remaining = candidates[:len(candidates)], []
            else:
                chosen = candidates[:self.NUM_SLOTS-1]
                remaining = candidates[self.NUM_SLOTS-1:]
            chosen = list(map(lambda x: x[0], chosen))
            remaining = list(map(lambda x: x[0], remaining))
            
            if self.choke_turn_cntr == 0 or\
                    self.optunchoked == self.NO_UNCHOKED or\
                    not unchoked_requesting:
                # time to unchoke based on turn count OR
                # prev rnd no unchoke, choke this round
                self.choke_turn_cntr = 0
                if len(remaining) == 0:
                    pass
                else:
                    self.optunchoked = random.choice(remaining)
                    chosen.append(self.optunchoked)
                    self.choke_turn_cntr += 1
                    self.choke_turn_cntr %= 3
            else:
                chosen.append(self.optunchoked)
                self.choke_turn_cntr += 1
                self.choke_turn_cntr %= 3

            bws = []
            if len(chosen) > 0:
                bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
