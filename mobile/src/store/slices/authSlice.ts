/**
 * Authentication State Slice
 */
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import apiClient from '../../services/api/client';

interface User {
  id: string;
  did: string;
  displayName: string | null;
  role: string;
  isVerified: boolean;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  biometricEnabled: boolean;
  fidoRegistered: boolean;
}

const initialState: AuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
  biometricEnabled: false,
  fidoRegistered: false,
};

// Async thunks
export const loginWithDID = createAsyncThunk(
  'auth/loginWithDID',
  async (
    { verifiablePresentation, challenge }: { verifiablePresentation: object; challenge: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await apiClient.loginWithDID(verifiablePresentation, challenge);
      const user = await apiClient.getCurrentUser();
      return { ...response, user };
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Login failed');
    }
  }
);

export const fetchCurrentUser = createAsyncThunk(
  'auth/fetchCurrentUser',
  async (_, { rejectWithValue }) => {
    try {
      return await apiClient.getCurrentUser();
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Failed to fetch user');
    }
  }
);

export const registerFIDO = createAsyncThunk(
  'auth/registerFIDO',
  async (
    { attestationObject, clientDataJSON }: { attestationObject: string; clientDataJSON: string },
    { rejectWithValue }
  ) => {
    try {
      return await apiClient.registerFIDO(attestationObject, clientDataJSON);
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'FIDO registration failed');
    }
  }
);

export const logout = createAsyncThunk('auth/logout', async () => {
  await apiClient.logout();
});

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    setBiometricEnabled: (state, action: PayloadAction<boolean>) => {
      state.biometricEnabled = action.payload;
    },
    setFidoRegistered: (state, action: PayloadAction<boolean>) => {
      state.fidoRegistered = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Login with DID
      .addCase(loginWithDID.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(loginWithDID.fulfilled, (state, action) => {
        state.isLoading = false;
        state.isAuthenticated = true;
        state.user = action.payload.user;
      })
      .addCase(loginWithDID.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Fetch current user
      .addCase(fetchCurrentUser.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(fetchCurrentUser.fulfilled, (state, action) => {
        state.isLoading = false;
        state.user = action.payload;
        state.isAuthenticated = true;
      })
      .addCase(fetchCurrentUser.rejected, (state, action) => {
        state.isLoading = false;
        state.isAuthenticated = false;
        state.user = null;
      })
      // Register FIDO
      .addCase(registerFIDO.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(registerFIDO.fulfilled, (state) => {
        state.isLoading = false;
        state.fidoRegistered = true;
      })
      .addCase(registerFIDO.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Logout
      .addCase(logout.fulfilled, (state) => {
        state.user = null;
        state.isAuthenticated = false;
        state.fidoRegistered = false;
      });
  },
});

export const { clearError, setBiometricEnabled, setFidoRegistered } = authSlice.actions;
export default authSlice.reducer;
