/**
 * Ballot Screen - Main voting interface
 */
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  ScrollView,
  Alert,
  AccessibilityInfo,
} from 'react-native';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '../../store';
import { fetchElection } from '../../store/slices/electionSlice';
import {
  selectCandidate,
  requestVoteToken,
  submitVote,
  resetVote,
} from '../../store/slices/voteSlice';

interface Props {
  route: { params: { electionId: string } };
  navigation: any;
}

const BallotScreen: React.FC<Props> = ({ route, navigation }) => {
  const { electionId } = route.params;
  const dispatch = useDispatch<AppDispatch>();

  const { currentElection, isLoading: electionLoading } = useSelector(
    (state: RootState) => state.election
  );
  const { selectedCandidate, voteToken, step, isSubmitting, error } = useSelector(
    (state: RootState) => state.vote
  );

  const [showConfirmation, setShowConfirmation] = useState(false);

  useEffect(() => {
    dispatch(fetchElection(electionId));
    dispatch(requestVoteToken(electionId));

    return () => {
      dispatch(resetVote());
    };
  }, [dispatch, electionId]);

  useEffect(() => {
    if (error) {
      Alert.alert('Error', error);
    }
  }, [error]);

  const handleSelectCandidate = (symbolNumber: number) => {
    dispatch(selectCandidate(symbolNumber));
    // Announce selection for screen readers
    AccessibilityInfo.announceForAccessibility(
      `Selected candidate number ${symbolNumber}`
    );
  };

  const handleConfirmSelection = () => {
    if (!selectedCandidate) {
      Alert.alert('No Selection', 'Please select a candidate before proceeding.');
      return;
    }
    setShowConfirmation(true);
  };

  const handleSubmitVote = async () => {
    if (!selectedCandidate || !currentElection) return;

    try {
      // Mock merkle path for demonstration
      const merklePath = ['0x' + '0'.repeat(64), '0x' + '0'.repeat(64)];
      const merkleIndices = [0, 1];

      await dispatch(
        submitVote({
          electionId,
          choice: selectedCandidate,
          numCandidates: currentElection.candidates.length,
          merklePath,
          merkleIndices,
        })
      ).unwrap();

      navigation.navigate('Receipt');
    } catch (error) {
      // Error handled by redux
    }
  };

  const handleCancelConfirmation = () => {
    setShowConfirmation(false);
  };

  if (electionLoading || !currentElection) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <Text>Loading ballot...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (showConfirmation) {
    const selected = currentElection.candidates.find(
      (c) => c.symbolNumber === selectedCandidate
    );

    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.confirmationContainer}>
          <Text style={styles.confirmationTitle}>Confirm Your Vote</Text>

          <View style={styles.selectedCandidateCard}>
            <Text style={styles.selectedLabel}>You selected:</Text>
            <View style={styles.selectedSymbol}>
              <Text style={styles.selectedSymbolText}>{selected?.symbolNumber}</Text>
            </View>
            <Text style={styles.selectedName}>{selected?.name}</Text>
            {selected?.party && (
              <Text style={styles.selectedParty}>{selected.party}</Text>
            )}
          </View>

          <Text style={styles.confirmationWarning}>
            ⚠️ This action cannot be undone. Your vote will be encrypted and
            recorded on the blockchain.
          </Text>

          <View style={styles.confirmationButtons}>
            <TouchableOpacity
              style={styles.cancelButton}
              onPress={handleCancelConfirmation}
              accessibilityRole="button"
              accessibilityLabel="Go back and change selection"
            >
              <Text style={styles.cancelButtonText}>Change Selection</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.submitButton, isSubmitting && styles.disabledButton]}
              onPress={handleSubmitVote}
              disabled={isSubmitting}
              accessibilityRole="button"
              accessibilityLabel="Confirm and submit vote"
            >
              <Text style={styles.submitButtonText}>
                {isSubmitting ? 'Submitting...' : 'Confirm Vote'}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.electionTitle} accessibilityRole="header">
          {currentElection.title}
        </Text>
        <Text style={styles.instructions}>
          Select one candidate by tapping on their card
        </Text>
      </View>

      <ScrollView style={styles.candidateList} contentContainerStyle={styles.candidateListContent}>
        {currentElection.candidates.map((candidate) => (
          <TouchableOpacity
            key={candidate.id}
            style={[
              styles.candidateCard,
              selectedCandidate === candidate.symbolNumber && styles.selectedCard,
            ]}
            onPress={() => handleSelectCandidate(candidate.symbolNumber)}
            accessibilityRole="radio"
            accessibilityState={{ checked: selectedCandidate === candidate.symbolNumber }}
            accessibilityLabel={`Candidate ${candidate.symbolNumber}: ${candidate.name}${
              candidate.party ? `, ${candidate.party}` : ''
            }`}
          >
            <View style={styles.symbolContainer}>
              <Text
                style={[
                  styles.symbolNumber,
                  selectedCandidate === candidate.symbolNumber && styles.selectedSymbolNumber,
                ]}
              >
                {candidate.symbolNumber}
              </Text>
            </View>

            <View style={styles.candidateInfo}>
              <Text style={styles.candidateName}>{candidate.name}</Text>
              {candidate.party && (
                <Text style={styles.candidateParty}>{candidate.party}</Text>
              )}
            </View>

            {selectedCandidate === candidate.symbolNumber && (
              <View style={styles.checkmark}>
                <Text style={styles.checkmarkText}>✓</Text>
              </View>
            )}
          </TouchableOpacity>
        ))}
      </ScrollView>

      <View style={styles.footer}>
        <TouchableOpacity
          style={[styles.confirmButton, !selectedCandidate && styles.disabledButton]}
          onPress={handleConfirmSelection}
          disabled={!selectedCandidate}
          accessibilityRole="button"
          accessibilityLabel="Proceed to confirmation"
          accessibilityState={{ disabled: !selectedCandidate }}
        >
          <Text style={styles.confirmButtonText}>
            {selectedCandidate ? 'Proceed to Confirmation' : 'Select a Candidate'}
          </Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  electionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 8,
  },
  instructions: {
    fontSize: 14,
    color: '#6B7280',
  },
  candidateList: {
    flex: 1,
  },
  candidateListContent: {
    padding: 16,
  },
  candidateCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: '#E5E7EB',
  },
  selectedCard: {
    borderColor: '#1a56db',
    backgroundColor: '#EFF6FF',
  },
  symbolContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  symbolNumber: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#374151',
  },
  selectedSymbolNumber: {
    color: '#1a56db',
  },
  candidateInfo: {
    flex: 1,
  },
  candidateName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
  },
  candidateParty: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  checkmark: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#1a56db',
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkmarkText: {
    fontSize: 18,
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  footer: {
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  confirmButton: {
    backgroundColor: '#1a56db',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    minHeight: 48,
  },
  confirmButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  disabledButton: {
    backgroundColor: '#D1D5DB',
  },
  // Confirmation modal styles
  confirmationContainer: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
  },
  confirmationTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#111827',
    textAlign: 'center',
    marginBottom: 32,
  },
  selectedCandidateCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    marginBottom: 24,
    borderWidth: 2,
    borderColor: '#1a56db',
  },
  selectedLabel: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 16,
  },
  selectedSymbol: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#1a56db',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  selectedSymbolText: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  selectedName: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#111827',
    textAlign: 'center',
  },
  selectedParty: {
    fontSize: 16,
    color: '#6B7280',
    marginTop: 4,
  },
  confirmationWarning: {
    fontSize: 14,
    color: '#92400E',
    backgroundColor: '#FEF3C7',
    padding: 16,
    borderRadius: 12,
    marginBottom: 24,
    textAlign: 'center',
  },
  confirmationButtons: {
    gap: 12,
  },
  cancelButton: {
    backgroundColor: '#F3F4F6',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    minHeight: 48,
    marginBottom: 12,
  },
  cancelButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
  },
  submitButton: {
    backgroundColor: '#059669',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    minHeight: 48,
  },
  submitButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});

export default BallotScreen;
