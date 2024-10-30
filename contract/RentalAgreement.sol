// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract RentalAgreement {
    address public owner;

    struct Agreement {
        uint256 apartmentId;
        bytes32 agreementHash;
        bytes32 userIdHash;
        uint256 timestamp;
    }

    mapping(uint256 => Agreement) public agreements;

    event AgreementRecorded(
        uint256 indexed apartmentId,
        bytes32 agreementHash,
        bytes32 userIdHash,
        uint256 timestamp
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function.");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function recordAgreement(
        uint256 _apartmentId,
        bytes32 _agreementHash,
        bytes32 _userIdHash
    ) public onlyOwner {
        agreements[_apartmentId] = Agreement(
            _apartmentId,
            _agreementHash,
            _userIdHash,
            block.timestamp
        );
        emit AgreementRecorded(_apartmentId, _agreementHash, _userIdHash, block.timestamp);
    }

    // Optional: Function to retrieve agreement details
    function getAgreement(uint256 _apartmentId) public view returns (Agreement memory) {
        return agreements[_apartmentId];
    }
}