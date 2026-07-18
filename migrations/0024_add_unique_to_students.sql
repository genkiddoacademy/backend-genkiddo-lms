-- Mencegah duplikasi profil siswa dengan nama yang sama di bawah satu orang tua
-- Digunakan untuk menstabilkan alur perpanjangan (renewal) agar tidak membuat profil baru
ALTER TABLE students ADD CONSTRAINT unique_parent_child_name UNIQUE (parent_id, name);
