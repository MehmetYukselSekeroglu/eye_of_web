-- PostgreSQL için kullanıcı tablosu şeması

CREATE TABLE users (
    id SERIAL PRIMARY KEY,                                      -- Benzersiz kullanıcı kimliği, otomatik artan
    username VARCHAR(255) UNIQUE NOT NULL,                      -- Kullanıcı adı, benzersiz ve boş olamaz
    password VARCHAR(255) NOT NULL,                             -- Şifrelenmiş kullanıcı parolası, boş olamaz
    email VARCHAR(255) UNIQUE,                                  -- Kullanıcının e-posta adresi, benzersiz
    name VARCHAR(255),                                          -- Kullanıcının gerçek adı, boş olabilir
    is_active BOOLEAN DEFAULT TRUE NOT NULL,                    -- Hesap aktif mi? Varsayılan: TRUE
    is_admin BOOLEAN DEFAULT FALSE NOT NULL,                    -- Kullanıcı admin mi? Varsayılan: FALSE
    is_owner BOOLEAN DEFAULT FALSE NOT NULL,                    -- Kullanıcı sahip mi? Varsayılan: FALSE
    is_demo BOOLEAN DEFAULT FALSE NOT NULL,                     -- Demo hesabı mı? Varsayılan: FALSE
    create_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, -- Hesap oluşturulma tarihi
    demo_start TIMESTAMP WITH TIME ZONE,                            -- Demo başlangıç tarihi, boş olabilir
    demo_end TIMESTAMP WITH TIME ZONE,                              -- Demo bitiş tarihi, boş olabilir
    subscription_start_date TIMESTAMP WITH TIME ZONE,               -- Abonelik başlangıç tarihi
    subscription_end_date TIMESTAMP WITH TIME ZONE,                 -- Abonelik bitiş tarihi
    last_login TIMESTAMP WITH TIME ZONE,                            -- Son giriş tarihi, boş olabilir

    -- Demo bitiş tarihi, başlangıç tarihinden sonra olmalı (eğer her ikisi de belirtilmişse)
    CONSTRAINT check_demo_dates CHECK (demo_start IS NULL OR demo_end IS NULL OR demo_end > demo_start),
    -- Abonelik bitiş tarihi, başlangıç tarihinden sonra olmalı (eğer her ikisi de belirtilmişse)
    CONSTRAINT check_subscription_dates CHECK (subscription_start_date IS NULL OR subscription_end_date IS NULL OR subscription_end_date > subscription_start_date)
);

-- Kullanıcı adı üzerinde hızlı arama için indeks (isteğe bağlı ama önerilir)
CREATE INDEX idx_users_username ON users (username);
-- E-posta üzerinde hızlı arama için indeks (isteğe bağlı ama önerilir)
CREATE INDEX idx_users_email ON users (email);

-- Örnek Admin Kullanıcısı (Parola Flask tarafında hash'lenip buraya eklenecek)
-- INSERT INTO users (username, password, name, is_active, is_admin) 
-- VALUES ('admin', 'HASHED_PASSWORD_HERE', 'Admin User', TRUE, TRUE);

COMMENT ON TABLE users IS 'Uygulama kullanıcılarını saklayan tablo.';
COMMENT ON COLUMN users.id IS 'Kullanıcının benzersiz birincil anahtarı.';
COMMENT ON COLUMN users.username IS 'Kullanıcının sisteme giriş yaparken kullandığı benzersiz adı.';
COMMENT ON COLUMN users.password IS 'Flask tarafından hashlenmiş kullanıcı parolası.';
COMMENT ON COLUMN users.email IS 'Kullanıcının e-posta adresi.';
COMMENT ON COLUMN users.name IS 'Kullanıcının tam adı.';
COMMENT ON COLUMN users.is_active IS 'Kullanıcı hesabının aktif olup olmadığını belirtir (TRUE=aktif).';
COMMENT ON COLUMN users.is_admin IS 'Kullanıcının admin yetkilerine sahip olup olmadığını belirtir (TRUE=admin).';
COMMENT ON COLUMN users.is_owner IS 'Kullanıcının sahip (owner) yetkilerine sahip olup olmadığını belirtir (TRUE=owner).';
COMMENT ON COLUMN users.is_demo IS 'Kullanıcı hesabının bir demo hesabı olup olmadığını belirtir (TRUE=demo).';
COMMENT ON COLUMN users.create_date IS 'Kullanıcı hesabının oluşturulduğu tarih ve saat.';
COMMENT ON COLUMN users.demo_start IS 'Demo hesabının başlangıç tarihi ve saati.';
COMMENT ON COLUMN users.demo_end IS 'Demo hesabının bitiş tarihi ve saati.';
COMMENT ON COLUMN users.subscription_start_date IS 'Kullanıcının aboneliğinin başlangıç tarihi ve saati.';
COMMENT ON COLUMN users.subscription_end_date IS 'Kullanıcının aboneliğinin bitiş tarihi ve saati.';
COMMENT ON COLUMN users.last_login IS 'Kullanıcının sisteme son giriş yaptığı tarih ve saat.';
