/**
 * Election State Slice
 */
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import apiClient from '../../services/api/client';

interface Candidate {
  id: string;
  name: string;
  party: string | null;
  symbolNumber: number;
  photoUrl: string | null;
}

interface Election {
  id: string;
  title: string;
  description: string | null;
  status: string;
  startTime: string;
  endTime: string;
  candidates: Candidate[];
  totalCandidates: number;
  isActive: boolean;
}

interface ElectionState {
  elections: Election[];
  activeElections: Election[];
  currentElection: Election | null;
  isLoading: boolean;
  error: string | null;
}

const initialState: ElectionState = {
  elections: [],
  activeElections: [],
  currentElection: null,
  isLoading: false,
  error: null,
};

// Async thunks
export const fetchElections = createAsyncThunk(
  'election/fetchElections',
  async (_, { rejectWithValue }) => {
    try {
      return await apiClient.getElections();
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Failed to fetch elections');
    }
  }
);

export const fetchActiveElections = createAsyncThunk(
  'election/fetchActiveElections',
  async (_, { rejectWithValue }) => {
    try {
      return await apiClient.getActiveElections();
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Failed to fetch active elections');
    }
  }
);

export const fetchElection = createAsyncThunk(
  'election/fetchElection',
  async (electionId: string, { rejectWithValue }) => {
    try {
      return await apiClient.getElection(electionId);
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Failed to fetch election');
    }
  }
);

const electionSlice = createSlice({
  name: 'election',
  initialState,
  reducers: {
    clearCurrentElection: (state) => {
      state.currentElection = null;
    },
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch all elections
      .addCase(fetchElections.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchElections.fulfilled, (state, action) => {
        state.isLoading = false;
        state.elections = action.payload;
      })
      .addCase(fetchElections.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Fetch active elections
      .addCase(fetchActiveElections.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchActiveElections.fulfilled, (state, action) => {
        state.isLoading = false;
        state.activeElections = action.payload;
      })
      .addCase(fetchActiveElections.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Fetch single election
      .addCase(fetchElection.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchElection.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentElection = action.payload;
      })
      .addCase(fetchElection.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearCurrentElection, clearError } = electionSlice.actions;
export default electionSlice.reducer;
