/**
 * API Client for the Voting Backend
 */
import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'https://api.voting.example.com/api/v1';

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    // Request interceptor - add auth token
    this.client.interceptors.request.use(
      async (config) => {
        if (this.accessToken) {
          config.headers.Authorization = `Bearer ${this.accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            const newToken = await this.refreshAccessToken();
            if (newToken && originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              return this.client(originalRequest);
            }
          } catch (refreshError) {
            // Token refresh failed - logout user
            await this.logout();
            throw refreshError;
          }
        }

        return Promise.reject(error);
      }
    );
  }

  async initialize(): Promise<void> {
    this.accessToken = await AsyncStorage.getItem('accessToken');
    this.refreshToken = await AsyncStorage.getItem('refreshToken');
  }

  async setTokens(accessToken: string, refreshToken: string): Promise<void> {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    await AsyncStorage.setItem('accessToken', accessToken);
    await AsyncStorage.setItem('refreshToken', refreshToken);
  }

  async clearTokens(): Promise<void> {
    this.accessToken = null;
    this.refreshToken = null;
    await AsyncStorage.removeItem('accessToken');
    await AsyncStorage.removeItem('refreshToken');
  }

  private async refreshAccessToken(): Promise<string | null> {
    if (!this.refreshToken) return null;

    try {
      const response = await axios.post(`${API_BASE_URL}/auth/token/refresh`, {
        refresh_token: this.refreshToken,
      });

      const { access_token, refresh_token } = response.data;
      await this.setTokens(access_token, refresh_token);
      return access_token;
    } catch (error) {
      return null;
    }
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/auth/logout');
    } finally {
      await this.clearTokens();
    }
  }

  // Auth endpoints
  async getDIDChallenge(): Promise<{ challenge: string; domain: string }> {
    const response = await this.client.post('/auth/did/challenge');
    return response.data;
  }

  async verifyDID(verifiablePresentation: object, challenge: string): Promise<any> {
    const response = await this.client.post('/auth/did/verify', {
      verifiable_presentation: verifiablePresentation,
      challenge,
    });
    return response.data;
  }

  async loginWithDID(verifiablePresentation: object, challenge: string): Promise<any> {
    const response = await this.client.post('/auth/did/login', {
      verifiable_presentation: verifiablePresentation,
      challenge,
    });

    const { access_token, refresh_token } = response.data;
    await this.setTokens(access_token, refresh_token);

    return response.data;
  }

  async getFIDOChallenge(): Promise<any> {
    const response = await this.client.post('/auth/fido/challenge', {});
    return response.data;
  }

  async registerFIDO(attestationObject: string, clientDataJSON: string): Promise<any> {
    const response = await this.client.post('/auth/fido/register', {
      attestation_object: attestationObject,
      client_data_json: clientDataJSON,
    });
    return response.data;
  }

  async getCurrentUser(): Promise<any> {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  // Election endpoints
  async getElections(): Promise<any[]> {
    const response = await this.client.get('/elections');
    return response.data;
  }

  async getActiveElections(): Promise<any[]> {
    const response = await this.client.get('/elections/active');
    return response.data;
  }

  async getElection(electionId: string): Promise<any> {
    const response = await this.client.get(`/elections/${electionId}`);
    return response.data;
  }

  // Vote endpoints
  async requestVoteToken(electionId: string): Promise<any> {
    const response = await this.client.post('/votes/token', {
      election_id: electionId,
    });
    return response.data;
  }

  async submitVote(
    electionId: string,
    voteToken: string,
    encryptedVote: string,
    nullifier: string,
    eligibilityProof: string,
    validityProof: string
  ): Promise<any> {
    const response = await this.client.post('/votes/submit', {
      election_id: electionId,
      vote_token: voteToken,
      encrypted_vote: encryptedVote,
      nullifier,
      eligibility_proof: eligibilityProof,
      validity_proof: validityProof,
    });
    return response.data;
  }

  async getVoteReceipt(verificationCode: string): Promise<any> {
    const response = await this.client.get(`/votes/receipt/${verificationCode}`);
    return response.data;
  }

  async checkVoteStatus(electionId: string): Promise<any> {
    const response = await this.client.get(`/votes/status/${electionId}`);
    return response.data;
  }

  async getBallot(electionId: string): Promise<any> {
    const response = await this.client.get(`/votes/ballot/${electionId}`);
    return response.data;
  }

  // Verification endpoints
  async verifyCastAsIntended(verificationCode: string): Promise<any> {
    const response = await this.client.get(`/verification/cast/${verificationCode}`);
    return response.data;
  }

  // Tally endpoints
  async getTallyResults(electionId: string): Promise<any> {
    const response = await this.client.get(`/tally/results/${electionId}`);
    return response.data;
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }
}

export const apiClient = new ApiClient();
export default apiClient;
