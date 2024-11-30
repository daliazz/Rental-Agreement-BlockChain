// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract RentalAgreement {
    address public owner;
    address public tenant;
    uint256 public rentAmount;
    uint256 public leaseDuration;
    bool public isSigned;

    struct Agreement {
        uint256 apartmentId;
        bytes32 agreementHash;
        bytes32 userIdHash;
        uint256 timestamp;
    }

    struct Payment {
        uint256 amount;
        uint256 timestamp;
    }

    mapping(uint256 => Agreement) public agreements;
    Payment[] public paymentHistory;

    event AgreementRecorded(uint256 indexed apartmentId, bytes32 agreementHash, bytes32 userIdHash, uint256 timestamp);
    event PaymentRecorded(uint256 amount, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function.");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function setRentAmount(uint256 _rentAmount) public onlyOwner {
        rentAmount = _rentAmount;
    }

    function setLeaseDuration(uint256 _leaseDuration) public onlyOwner {
        leaseDuration = _leaseDuration;
    }

    // New function to set rent amount and lease duration in one call
    function setAgreementDetails(uint256 _rentAmount, uint256 _leaseDuration) public onlyOwner {
        rentAmount = _rentAmount;
        leaseDuration = _leaseDuration;
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

    function signAgreement(address _tenant) public onlyOwner {
        require(!isSigned, "Agreement already signed.");
        tenant = _tenant;
        isSigned = true;
    }

    function recordPayment(uint256 _amount) public {
        require(msg.sender == tenant, "Only tenant can make payments.");
        paymentHistory.push(Payment(_amount, block.timestamp));
        emit PaymentRecorded(_amount, block.timestamp);
    }

    function getAgreement(uint256 _apartmentId) public view returns (Agreement memory) {
        return agreements[_apartmentId];
    }
}