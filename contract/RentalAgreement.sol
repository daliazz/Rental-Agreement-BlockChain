// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract RentalAgreement {
    address public tenant;
    address public landlord;
    uint256 public rentAmount;
    uint256 public leaseDuration;
    uint256 public startDate;
    bool public isSigned;

    enum ContractState {
        Pending,
        Active,
        Completed,
        Terminated
    }
    ContractState public state;

    // Events
    event AgreementCreated(
        address indexed tenant,
        address indexed landlord,
        uint256 rentAmount,
        uint256 leaseDuration
    );
    event AgreementSigned(
        address indexed signer,
        bool isSigned,
        ContractState state
    );
    event PaymentMade(address indexed tenant, uint256 amount);
    event AgreementTerminated(
        address indexed terminatedBy,
        uint256 terminationDate
    );

    // Modifiers
    modifier onlyRole(address _role) {
        require(msg.sender == _role, "Unauthorized.");
        _;
    }

    constructor(
        address _landlord,
        address _tenant,
        uint256 _rentAmount,
        uint256 _leaseDuration
    ) {
        require(_tenant != address(0), "Tenant required.");
        landlord = _landlord;
        tenant = _tenant;
        rentAmount = _rentAmount;
        leaseDuration = _leaseDuration;
        state = ContractState.Pending;
        emit AgreementCreated(_tenant, _landlord, _rentAmount, _leaseDuration);
    }

    function signAgreement() public {
        require(state == ContractState.Pending, "Not pending.");
        if (msg.sender == landlord && !isSigned) {
            isSigned = true;
            emit AgreementSigned(msg.sender, isSigned, state); // Log landlord's signing
        } else if (msg.sender == tenant) {
            require(isSigned, "Landlord must sign first.");
            state = ContractState.Active;
            startDate = block.timestamp;
            emit AgreementSigned(msg.sender, isSigned, state); // Log tenant's signing
        } else {
            revert("Unauthorized signer.");
        }
    }

    function makePayment() public payable onlyRole(tenant) {
        require(state == ContractState.Active, "Not active.");
        require(msg.value == rentAmount, "Incorrect rent.");
        payable(landlord).transfer(msg.value);
        emit PaymentMade(msg.sender, msg.value);
        if ((block.timestamp - startDate) / 30 days >= leaseDuration) {
            state = ContractState.Completed;
        }
    }

    function terminateAgreement() public {
        require(state != ContractState.Completed, "Already completed.");
        require(
            msg.sender == landlord || msg.sender == tenant,
            "Unauthorized."
        );
        if (state == ContractState.Active && msg.sender == landlord) {
            uint256 refund = (leaseDuration -
                (block.timestamp - startDate) /
                30 days) * rentAmount;
            payable(tenant).transfer(refund);
        }
        state = ContractState.Terminated;
        emit AgreementTerminated(msg.sender, block.timestamp);
    }
}
