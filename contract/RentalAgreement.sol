// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract RentalAgreement {
    address public tenant;
    address public landlord;
    uint256 public rentAmount;
    uint256 public leaseDuration; // in months
    uint256 public startDate;
    bool public isSigned;

    enum ContractState { Pending, Active, Completed, Terminated }
    ContractState public state;

    event AgreementCreated(address indexed tenant, address indexed landlord, uint256 rentAmount, uint256 leaseDuration);
    event AgreementSigned(address indexed signer);
    event PaymentMade(address indexed tenant, uint256 amount);
    event AgreementCompleted();
    event AgreementTerminated(address indexed terminatedBy, uint256 terminationDate);

    modifier onlyLandlord() {
        require(msg.sender == landlord, "Only landlord can perform this action.");
        _;
    }

    modifier onlyTenant() {
        require(msg.sender == tenant, "Only tenant can perform this action.");
        _;
    }

constructor(address _landlord, uint256 _rentAmount, uint256 _leaseDuration) {
    landlord = _landlord;
    rentAmount = _rentAmount;
    leaseDuration = _leaseDuration;
    state = ContractState.Pending;
    emit AgreementCreated(address(0), _landlord, _rentAmount, _leaseDuration);
}


 function signAgreement() public {
    require(state == ContractState.Pending, "Agreement not in pending state.");

    if (msg.sender == landlord && !isSigned) {
        isSigned = true;
    } else if (msg.sender == tenant && tenant != address(0)) {
        require(tenant == msg.sender, "Only the designated tenant can sign.");
    } else {
        revert("Unauthorized signer.");
    }

    emit AgreementSigned(msg.sender);

    // Transition to Active only when both parties sign
    if (tenant != address(0) && isSigned) {
        state = ContractState.Active;
        startDate = block.timestamp;
    }
}


    function makePayment() public payable onlyTenant {
        require(state == ContractState.Active, "Agreement is not active.");
        require(msg.value == rentAmount, "Incorrect rent amount.");

        payable(landlord).transfer(msg.value);
        emit PaymentMade(msg.sender, msg.value);

        uint256 monthsElapsed = (block.timestamp - startDate) / 30 days;
        if (monthsElapsed >= leaseDuration) {
            state = ContractState.Completed;
            emit AgreementCompleted();
        }
    }

    function terminateAgreement() public {
        require(state == ContractState.Pending || state == ContractState.Active, "Agreement cannot be terminated.");
        require(msg.sender == landlord || msg.sender == tenant, "Only landlord or tenant can terminate.");

        if (state == ContractState.Active) {
            uint256 monthsElapsed = (block.timestamp - startDate) / 30 days;
            uint256 remainingMonths = leaseDuration > monthsElapsed ? leaseDuration - monthsElapsed : 0;

            if (remainingMonths > 0 && msg.sender == landlord) {
                uint256 refundAmount = remainingMonths * rentAmount;
                payable(tenant).transfer(refundAmount);
            }
        }

        state = ContractState.Terminated;
        emit AgreementTerminated(msg.sender, block.timestamp);
    }
}
