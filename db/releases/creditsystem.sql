Alter table `user` Add column available_credits int Not NULL DEFAULT 0 After assigned_class_id
CREATE TABLE transactions (
    id INT NOT NULL AUTO_INCREMENT,
    teacher_id INT NOT NULL DEFAULT 0,
    type_of_transaction ENUM('credit', 'debit') NOT NULL,
    mode_of_payment ENUM('cash','online') ,
    student_id INT NOT NULL,
    action_performer_user_id INT NOT NULL,
    balance_before_this_transaction INT,
    balance_after_this_transaction INT, -- Note: spelling kept as requested
    amount_added INT,
    credits_added INT,
    total_available_credits INT,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Good practice for transaction logs
    PRIMARY KEY (id)
);
