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

from math import floor

class MMJWPropshare(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
    
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
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            for piece_id in list(isect):
                if not piece_id in piece_counts:
                    piece_counts[piece_id] = 0
                piece_counts[piece_id] += 1
        rarest_first = list(piece_counts.items())[:]
        random.shuffle(rarest_first)
        rarest_first = sorted(rarest_first, key = lambda x: x[1])
        # logging.debug("Piece set for {} = {}".format(self.id, self.pieces))
        for peer in peers:
            cur_len = 0
            for piece_id, _counts in rarest_first:
                if cur_len >= self.max_requests:
                    break
                if not piece_id in peer.available_pieces:
                    continue
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

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            # declare propshare constants
            OPTIM_UNCHOKE_RATIO = 0.1 # ratio of bw to use for optim unchoke

            # check previous round for who we downloaded from
            prev_round_dt = history.downloads[round_num - 1]
            prev_rnd_bw = {} # id |-> total size
            for dl_obj in prev_round_dt:
                if not dl_obj.from_id in prev_rnd_bw:
                    prev_rnd_bw[dl_obj.from_id] = 0
                prev_rnd_bw[dl_obj.from_id] += dl_obj.blocks
            
            chosen_req_bw = {} # dict id -> total bw from prev. round
            optim_candidates = [] # for optimistic unchoking
            for cur_req in requests:
                if cur_req.requester_id in prev_rnd_bw:
                    chosen_req_bw[cur_req.requester_id] = 0
                else:
                    optim_candidates.append(cur_req.requester_id)
            tot_bws = 0
            for req_id in chosen_req_bw.keys():
                chosen_req_bw[req_id] += prev_rnd_bw[req_id]
                tot_bws += prev_rnd_bw[req_id]

            # So we're supposed to floor these (source: Ed PS2 Megathread)
            adjusted_bws_sum = 0
            if len(optim_candidates) == 0:
                OPTIM_UNCHOKE_RATIO = 0
            for i in chosen_req_bw.keys():
                chosen_req_bw[i] *= self.up_bw * (1 - OPTIM_UNCHOKE_RATIO)
                chosen_req_bw[i] /= tot_bws
                chosen_req_bw[i] = floor(chosen_req_bw[i])
                adjusted_bws_sum += chosen_req_bw[i]
            if len(optim_candidates) > 0:
                optim_id = random.choice(optim_candidates)
                chosen_req_bw[optim_id] = floor(self.up_bw * OPTIM_UNCHOKE_RATIO)
                adjusted_bws_sum += chosen_req_bw[optim_id]
            rem = self.up_bw - adjusted_bws_sum
            for i in random.choices(list(chosen_req_bw.keys()), k = max(0, rem)):
                chosen_req_bw[i] += 1

            chosen = chosen_req_bw.keys()
            bws = chosen_req_bw.values()

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
