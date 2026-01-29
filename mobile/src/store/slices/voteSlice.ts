/**
 * Vote State Slice
 */
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import apiClient from '../../services/api/client';
import {
  prepareVote,
  getVoterSecret,
  generateVoterSecret,
  storeVoterSecret,
  createVoterCommitment,
} from '../../services/crypto/encryption';

interface VoteToken {
  token: string;
  expiresAt: string;
  electionId: string;
  electionPublicKey: string;
}

interface VoteReceipt {
  verificationCode: string;
  electionId: string;
  electionTitle: string;
  encryptedVoteHash: string;
  blockchainTxId: string | null;
  createdAt: string;
}

interface VoteState {
  voteToken: VoteToken | null;
  selectedCandidate: number | null;
  isSubmitting: boolean;
  receipt: VoteReceipt | null;
  voteStatus: { [electionId: string]: boolean };
  error: string | null;
  step: 'idle' | 'token' | 'voting' | 'submitting' | 'complete';
}

const initialState: VoteState = {
  voteToken: null,
  selectedCandidate: null,
  isSubmitting: false,
  receipt: null,
  voteStatus: {},
  error: null,
  step: 'idle',
};

// Async thunks
export const requestVoteToken = createAsyncThunk(
  'vote/requestVoteToken',
  async (electionId: string, { rejectWithValue }) => {
    try {
      return await apiClient.requestVoteToken(electionId);
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Failed to get vote token');
    }
  }
);

export const submitVote = createAsyncThunk(
  'vote/submitVote',
  async (
    {
      electionId,
      choice,
      numCandidates,
      merklePath,
      merkleIndices,
    }: {
      electionId: string;
      choice: number;
      numCandidates: number;
      merklePath: string[];
      merkleIndices: number[];
    },
    { getState, rejectWithValue }
  ) => {
    try {
      const state = getState() as { vote: VoteState };
      const { voteToken } = state.vote;

      if (!voteToken) {
        return rejectWithValue('Vote token not available');
      }

      // Get or generate voter secret
      let voterSecret = await getVoterSecret();
      if (!voterSecret) {
        voterSecret = generateVoterSecret();
        await storeVoterSecret(voterSecret);
      }

      // Create voter commitment
      const voterCommitment = createVoterCommitment('voter-id', voterSecret);

      // Prepare the encrypted vote and proofs
      const { encryptedVote, proofs } = await prepareVote(
        choice,
        numCandidates,
        voteToken.electionPublicKey,
        voterSecret,
        voterCommitment,
        merklePath,
        merkleIndices,
        electionId
      );

      // Submit to backend
      const response = await apiClient.submitVote(
        electionId,
        voteToken.token,
        encryptedVote.ciphertext,
        proofs.nullifier,
        proofs.eligibilityProof,
        proofs.validityProof
      );

      return response;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Failed to submit vote');
    }
  }
);

export const checkVoteStatus = createAsyncThunk(
  'vote/checkVoteStatus',
  async (electionId: string, { rejectWithValue }) => {
    try {
      const response = await apiClient.checkVoteStatus(electionId);
      return { electionId, hasVoted: response.has_voted };
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Failed to check vote status');
    }
  }
);

export const fetchVoteReceipt = createAsyncThunk(
  'vote/fetchVoteReceipt',
  async (verificationCode: string, { rejectWithValue }) => {
    try {
      return await apiClient.getVoteReceipt(verificationCode);
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Failed to fetch receipt');
    }
  }
);

const voteSlice = createSlice({
  name: 'vote',
  initialState,
  reducers: {
    selectCandidate: (state, action: PayloadAction<number>) => {
      state.selectedCandidate = action.payload;
    },
    clearSelection: (state) => {
      state.selectedCandidate = null;
    },
    resetVote: (state) => {
      state.voteToken = null;
      state.selectedCandidate = null;
      state.receipt = null;
      state.error = null;
      state.step = 'idle';
    },
    clearError: (state) => {
      state.error = null;
    },
    setStep: (state, action: PayloadAction<VoteState['step']>) => {
      state.step = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Request vote token
      .addCase(requestVoteToken.pending, (state) => {
        state.error = null;
        state.step = 'token';
      })
      .addCase(requestVoteToken.fulfilled, (state, action) => {
        state.voteToken = {
          token: action.payload.token,
          expiresAt: action.payload.expires_at,
          electionId: action.payload.election_id,
          electionPublicKey: action.payload.election_public_key,
        };
        state.step = 'voting';
      })
      .addCase(requestVoteToken.rejected, (state, action) => {
        state.error = action.payload as string;
        state.step = 'idle';
      })
      // Submit vote
      .addCase(submitVote.pending, (state) => {
        state.isSubmitting = true;
        state.error = null;
        state.step = 'submitting';
      })
      .addCase(submitVote.fulfilled, (state, action) => {
        state.isSubmitting = false;
        state.receipt = {
          verificationCode: action.payload.verification_code,
          electionId: state.voteToken?.electionId || '',
          electionTitle: '',
          encryptedVoteHash: action.payload.encrypted_vote_hash,
          blockchainTxId: action.payload.blockchain_tx_id,
          createdAt: action.payload.timestamp,
        };
        state.voteToken = null;
        state.selectedCandidate = null;
        state.step = 'complete';
        if (state.receipt.electionId) {
          state.voteStatus[state.receipt.electionId] = true;
        }
      })
      .addCase(submitVote.rejected, (state, action) => {
        state.isSubmitting = false;
        state.error = action.payload as string;
        state.step = 'voting';
      })
      // Check vote status
      .addCase(checkVoteStatus.fulfilled, (state, action) => {
        state.voteStatus[action.payload.electionId] = action.payload.hasVoted;
      })
      // Fetch receipt
      .addCase(fetchVoteReceipt.fulfilled, (state, action) => {
        state.receipt = {
          verificationCode: action.payload.verification_code,
          electionId: action.payload.election_id,
          electionTitle: action.payload.election_title,
          encryptedVoteHash: action.payload.encrypted_vote_hash,
          blockchainTxId: action.payload.blockchain_tx_id,
          createdAt: action.payload.created_at,
        };
      });
  },
});

export const { selectCandidate, clearSelection, resetVote, clearError, setStep } =
  voteSlice.actions;
export default voteSlice.reducer;
