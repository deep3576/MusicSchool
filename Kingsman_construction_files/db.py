# db.py — raw SQL only (no ORM)
from sqlalchemy import create_engine, text
from config import Config

# pooled engine
engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    future=True,
)

def ensure_schema():
    """Create/upgrade tables using plain MySQL DDL.
    Ensures users, consumer_profiles, contact_messages, employees, employee_status_log.
    All IDs are INT (signed). No ORM used.
    """
    sql_users = """
    CREATE TABLE IF NOT EXISTS users (
        id INT NOT NULL AUTO_INCREMENT,
        email VARCHAR(200) NOT NULL UNIQUE,
        full_name VARCHAR(200) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role ENUM('admin','consumer') NOT NULL DEFAULT 'consumer',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        INDEX idx_users_email (email)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    sql_consumer_profiles = """
    CREATE TABLE IF NOT EXISTS consumer_profiles (
        id INT NOT NULL AUTO_INCREMENT,
        user_id INT NOT NULL UNIQUE,
        full_name VARCHAR(200) NOT NULL,
        phone VARCHAR(40),
        address1 VARCHAR(200),
        address2 VARCHAR(200),
        city VARCHAR(100),
        province VARCHAR(100),
        postal_code VARCHAR(20),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        CONSTRAINT fk_consumer_user FOREIGN KEY (user_id) REFERENCES users(id)
          ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    sql_contact_messages = """
    CREATE TABLE IF NOT EXISTS contact_messages (
        id INT NOT NULL AUTO_INCREMENT,
        name VARCHAR(120) NOT NULL,
        email VARCHAR(200) NOT NULL,
        phone VARCHAR(40),
        subject VARCHAR(200),
        message TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        INDEX idx_contact_email (email),
        INDEX idx_contact_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    sql_employees = """
    CREATE TABLE IF NOT EXISTS employees (
        id INT NOT NULL AUTO_INCREMENT,
        full_name VARCHAR(200) NOT NULL,
        job_title VARCHAR(120),
        email VARCHAR(200),
        phone VARCHAR(40),
        daily_rate DECIMAL(10,2) NOT NULL,
        start_date DATE NULL,
        status ENUM('active','inactive') NOT NULL DEFAULT 'active',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        INDEX idx_emp_status (status),
        INDEX idx_emp_name (full_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    sql_employee_status_log = """
    CREATE TABLE IF NOT EXISTS employee_status_log (
        id INT NOT NULL AUTO_INCREMENT,
        employee_id INT NOT NULL,
        work_date DATE NOT NULL,
        status ENUM('present','absent','half-day','leave') NOT NULL DEFAULT 'present',
        sign_in DATETIME NULL,
        sign_out DATETIME NULL,
        notes VARCHAR(255),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uniq_emp_date (employee_id, work_date),
        INDEX idx_esl_emp (employee_id),
        INDEX idx_esl_date (work_date),
        CONSTRAINT fk_esl_employee FOREIGN KEY (employee_id) REFERENCES employees(id)
          ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    jobs="""
            CREATE TABLE IF NOT EXISTS jobs (
              id INT AUTO_INCREMENT PRIMARY KEY,
              job_number INT NOT NULL UNIQUE,          -- sequential, used to show 3-digit code
              title VARCHAR(255) NOT NULL,
              client_name VARCHAR(255),
              client_email VARCHAR(255),
              client_phone VARCHAR(50),
              status ENUM('planned','in-progress','on-hold','completed','cancelled') DEFAULT 'planned',
              start_date DATE NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """
    jobs_steps="""
            CREATE TABLE IF NOT EXISTS job_steps (
              id INT AUTO_INCREMENT PRIMARY KEY,
              job_id INT NOT NULL,
              step_key VARCHAR(64) NOT NULL,           -- start | framing | pour | dry | final
              step_name VARCHAR(255) NOT NULL,
              target_date DATE NULL,
              completed TINYINT(1) DEFAULT 0,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              CONSTRAINT fk_job_steps_job FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
              CONSTRAINT uq_job_step UNIQUE (job_id, step_key)
            )
        """

    with engine.begin() as conn:
        conn.execute(text(sql_users))
        conn.execute(text(sql_consumer_profiles))
        conn.execute(text(sql_contact_messages))
        conn.execute(text(sql_employees))
        conn.execute(text(sql_employee_status_log))
        conn.execute(text(jobs))
        conn.execute(text(jobs_steps))
