/*
 * Main entry point for the Vote Chaincode
 */

package main

import (
	"log"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
	"github.com/voting/chaincode/vote/contracts"
)

func main() {
	voteContract := new(contracts.VoteContract)

	chaincode, err := contractapi.NewChaincode(voteContract)
	if err != nil {
		log.Panicf("Error creating vote chaincode: %v", err)
	}

	chaincode.Info.Title = "VoteContract"
	chaincode.Info.Version = "1.0.0"
	chaincode.Info.Description = "Blockchain Voting System Chaincode"

	if err := chaincode.Start(); err != nil {
		log.Panicf("Error starting vote chaincode: %v", err)
	}
}
