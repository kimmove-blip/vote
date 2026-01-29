/**
 * Verification Screen - Cast-as-intended verification
 */
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import apiClient from '../../services/api/client';

interface VerificationResult {
  verified: boolean;
  electionId: string;
  electionTitle: string;
  encryptedVoteHash: string;
  blockchainConfirmed: boolean;
  blockchainTxId: string | null;
  blockNumber: string | null;
  castTime: string;
}

const VerificationScreen: React.FC = () => {
  const [verificationCode, setVerificationCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = async () => {
    if (!verificationCode.trim()) {
      Alert.alert('Error', 'Please enter a verification code');
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.verifyCastAsIntended(verificationCode.trim());
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Verification failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setVerificationCode('');
    setResult(null);
    setError(null);
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title} accessibilityRole="header">
          Vote Verification
        </Text>
        <Text style={styles.subtitle}>
          Verify that your vote was recorded correctly on the blockchain
        </Text>
      </View>

      {!result ? (
        <View style={styles.content}>
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Verification Code</Text>
            <TextInput
              style={styles.input}
              value={verificationCode}
              onChangeText={setVerificationCode}
              placeholder="Enter your verification code"
              placeholderTextColor="#9CA3AF"
              autoCapitalize="characters"
              autoCorrect={false}
              accessibilityLabel="Verification code input"
            />
          </View>

          {error && (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          <TouchableOpacity
            style={[styles.verifyButton, isLoading && styles.disabledButton]}
            onPress={handleVerify}
            disabled={isLoading}
            accessibilityRole="button"
            accessibilityLabel="Verify vote"
          >
            {isLoading ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text style={styles.verifyButtonText}>Verify</Text>
            )}
          </TouchableOpacity>

          <View style={styles.infoBox}>
            <Text style={styles.infoTitle}>What is verification?</Text>
            <Text style={styles.infoText}>
              Cast-as-intended verification allows you to confirm that your encrypted
              vote was recorded exactly as you submitted it, without revealing how
              you voted.
            </Text>
          </View>
        </View>
      ) : (
        <View style={styles.resultContainer}>
          <View
            style={[
              styles.resultIcon,
              result.verified ? styles.successIcon : styles.failIcon,
            ]}
          >
            <Text style={styles.resultEmoji}>
              {result.verified ? '✓' : '✗'}
            </Text>
          </View>

          <Text style={styles.resultTitle}>
            {result.verified ? 'Vote Verified' : 'Verification Failed'}
          </Text>

          {result.verified && (
            <View style={styles.resultDetails}>
              <View style={styles.resultRow}>
                <Text style={styles.resultLabel}>Election</Text>
                <Text style={styles.resultValue}>{result.electionTitle}</Text>
              </View>

              <View style={styles.resultRow}>
                <Text style={styles.resultLabel}>Blockchain Status</Text>
                <View
                  style={[
                    styles.statusBadge,
                    result.blockchainConfirmed
                      ? styles.confirmedBadge
                      : styles.pendingBadge,
                  ]}
                >
                  <Text
                    style={[
                      styles.statusText,
                      result.blockchainConfirmed
                        ? styles.confirmedText
                        : styles.pendingText,
                    ]}
                  >
                    {result.blockchainConfirmed ? 'Confirmed' : 'Pending'}
                  </Text>
                </View>
              </View>

              <View style={styles.resultRow}>
                <Text style={styles.resultLabel}>Vote Hash</Text>
                <Text style={styles.resultValueMono} numberOfLines={1}>
                  {result.encryptedVoteHash.slice(0, 20)}...
                </Text>
              </View>

              {result.blockchainTxId && (
                <View style={styles.resultRow}>
                  <Text style={styles.resultLabel}>Transaction</Text>
                  <Text style={styles.resultValueMono} numberOfLines={1}>
                    {result.blockchainTxId.slice(0, 20)}...
                  </Text>
                </View>
              )}

              <View style={styles.resultRow}>
                <Text style={styles.resultLabel}>Cast Time</Text>
                <Text style={styles.resultValue}>
                  {new Date(result.castTime).toLocaleString()}
                </Text>
              </View>
            </View>
          )}

          <TouchableOpacity
            style={styles.resetButton}
            onPress={handleReset}
            accessibilityRole="button"
            accessibilityLabel="Verify another vote"
          >
            <Text style={styles.resetButtonText}>Verify Another Vote</Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  header: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 24,
    paddingVertical: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#6B7280',
  },
  content: {
    padding: 24,
  },
  inputContainer: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 18,
    color: '#111827',
    fontFamily: 'Courier',
    letterSpacing: 2,
  },
  errorContainer: {
    backgroundColor: '#FEE2E2',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  errorText: {
    color: '#DC2626',
    fontSize: 14,
  },
  verifyButton: {
    backgroundColor: '#1a56db',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    minHeight: 48,
    marginBottom: 24,
  },
  verifyButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  disabledButton: {
    backgroundColor: '#9CA3AF',
  },
  infoBox: {
    backgroundColor: '#EFF6FF',
    borderRadius: 12,
    padding: 16,
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1E40AF',
    marginBottom: 8,
  },
  infoText: {
    fontSize: 14,
    color: '#3B82F6',
    lineHeight: 20,
  },
  resultContainer: {
    flex: 1,
    padding: 24,
    alignItems: 'center',
  },
  resultIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  successIcon: {
    backgroundColor: '#D1FAE5',
  },
  failIcon: {
    backgroundColor: '#FEE2E2',
  },
  resultEmoji: {
    fontSize: 40,
  },
  resultTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 24,
  },
  resultDetails: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    width: '100%',
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  resultRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  resultLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  resultValue: {
    fontSize: 14,
    color: '#111827',
    fontWeight: '500',
    flex: 1,
    textAlign: 'right',
    marginLeft: 12,
  },
  resultValueMono: {
    fontSize: 12,
    color: '#111827',
    fontFamily: 'Courier',
    flex: 1,
    textAlign: 'right',
    marginLeft: 12,
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  confirmedBadge: {
    backgroundColor: '#D1FAE5',
  },
  pendingBadge: {
    backgroundColor: '#FEF3C7',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  confirmedText: {
    color: '#059669',
  },
  pendingText: {
    color: '#D97706',
  },
  resetButton: {
    backgroundColor: '#F3F4F6',
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: 12,
    minHeight: 48,
  },
  resetButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
});

export default VerificationScreen;
