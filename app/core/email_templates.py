VERIFICATION_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verifikasi Akun GenKiddo</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #F8F9FA; margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }
    .email-container { max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 24px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
    .brand-header { background-color: #EF7F1F; padding: 30px 20px; text-align: center; }
    .brand-logo { color: #FFFFFF; font-size: 28px; font-weight: 900; letter-spacing: -1px; text-decoration: none; display: inline-block; }
    .email-body { padding: 40px 50px; text-align: center; }
    .title { color: #1F1F1F; font-size: 24px; font-weight: 800; margin-bottom: 15px; }
    .subtitle { color: #555555; font-size: 15px; line-height: 1.6; margin-bottom: 30px; }
    .btn-verify { display: inline-block; background-color: #EF7F1F; color: #FFFFFF !important; font-size: 15px; font-weight: 700; padding: 16px 40px; border-radius: 50px; text-decoration: none; box-shadow: 0 10px 20px rgba(239, 127, 31, 0.2); margin-bottom: 30px; }
    .fallback-link { font-size: 11px; color: #888888; word-break: break-all; margin-top: 20px; padding: 15px; background-color: #F8F9FA; border-radius: 12px; text-align: left; }
    .footer { padding: 30px 20px; background-color: #F8F9FA; text-align: center; border-top: 1px solid #EEEEEE; }
    .footer-text { font-size: 12px; color: #999999; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="email-container">
    <div class="brand-header">
      <img src="https://lh3.googleusercontent.com/d/1z4l9PuXoNFcJfwLTZn-D7zWq4ALjjxcf" alt="GenKiddo" style="height: 55px; border: 0; display: inline-block; vertical-align: middle;" />
    </div>
    <div class="email-body">
      <h2 class="title">Verifikasi Alamat Email Anda</h2>
      <p class="subtitle">Halo Parent! Terima kasih telah bergabung dengan GenKiddo. Klik tombol di bawah ini untuk memverifikasi akun Anda dan mulai memantau petualangan belajar coding si kecil.</p>
      
      <a href="{verification_url}" class="btn-verify" target="_blank">Verifikasi Akun Saya</a>
      
      <div class="fallback-link">
        Jika tombol di atas tidak berfungsi, salin tautan berikut ke browser Anda:<br>
        <a href="{verification_url}" style="color: #EF7F1F; text-decoration: none;">{verification_url}</a>
      </div>
    </div>
    <div class="footer">
      <p class="footer-text">
        © 2026 GenKiddo Academy. Semua Hak Dilindungi.<br>
        Jl. Teknik Kimia Keputih, Sukolilo Surabaya, Jawa Timur 60111.<br>
        Email ini dikirim secara otomatis, mohon tidak membalas.
      </p>
    </div>
  </div>
</body>
</html>
"""

RESET_PASSWORD_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Password GenKiddo</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #F8F9FA; margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }
    .email-container { max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 24px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
    .brand-header { background-color: #EF7F1F; padding: 30px 20px; text-align: center; }
    .brand-logo { color: #FFFFFF; font-size: 28px; font-weight: 900; letter-spacing: -1px; text-decoration: none; display: inline-block; }
    .email-body { padding: 40px 50px; text-align: center; }
    .title { color: #1F1F1F; font-size: 24px; font-weight: 800; margin-bottom: 15px; }
    .subtitle { color: #555555; font-size: 15px; line-height: 1.6; margin-bottom: 30px; }
    .btn-reset { display: inline-block; background-color: #1F1F1F; color: #FFFFFF !important; font-size: 15px; font-weight: 700; padding: 16px 40px; border-radius: 50px; text-decoration: none; box-shadow: 0 10px 20px rgba(0,0,0,0.1); margin-bottom: 30px; }
    .fallback-link { font-size: 11px; color: #888888; word-break: break-all; margin-top: 20px; padding: 15px; background-color: #F8F9FA; border-radius: 12px; text-align: left; }
    .warning-text { font-size: 12px; color: #A0A0A0; margin-top: 20px; }
    .footer { padding: 30px 20px; background-color: #F8F9FA; text-align: center; border-top: 1px solid #EEEEEE; }
    .footer-text { font-size: 12px; color: #999999; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="email-container">
    <div class="brand-header">
      <img src="https://lh3.googleusercontent.com/d/1z4l9PuXoNFcJfwLTZn-D7zWq4ALjjxcf" alt="GenKiddo" style="height: 55px; border: 0; display: inline-block; vertical-align: middle;" />
    </div>
    <div class="email-body">
      <h2 class="title">Permintaan Atur Ulang Password</h2>
      <p class="subtitle">Kami menerima permintaan untuk mengatur ulang kata sandi akun Anda. Klik tombol di bawah ini untuk menetapkan password baru.</p>
      
      <a href="{reset_url}" class="btn-reset" target="_blank">Reset Password Saya</a>
      
      <div class="fallback-link">
        Tautan ini hanya berlaku selama 1 jam:<br>
        <a href="{reset_url}" style="color: #EF7F1F; text-decoration: none;">{reset_url}</a>
      </div>
      <p class="warning-text">Jika Anda tidak meminta pengaturan ulang ini, silakan abaikan email ini dengan aman.</p>
    </div>
    <div class="footer">
      <p class="footer-text">
        © 2026 GenKiddo Academy. Semua Hak Dilindungi.<br>
        Jl. Teknik Kimia Keputih, Sukolilo Surabaya, Jawa Timur 60111.<br>
        Email ini dikirim secara otomatis, mohon tidak membalas.
      </p>
    </div>
  </div>
</body>
</html>
"""

INVOICE_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kuitansi Pembayaran GenKiddo</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #F8F9FA; margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }
    .email-container { max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 24px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
    .brand-header { background-color: #EF7F1F; padding: 35px 40px; }
    .brand-logo { color: #FFFFFF; font-size: 28px; font-weight: 900; text-decoration: none; float: left; }
    .invoice-title { color: #FFFFFF; font-size: 16px; font-weight: 700; float: right; margin-top: 10px; text-transform: uppercase; letter-spacing: 1px; }
    .email-body { padding: 40px; }
    .invoice-details { display: table; width: 100%; margin-bottom: 30px; }
    .invoice-col { display: table-cell; width: 50%; font-size: 13px; color: #666666; line-height: 1.6; vertical-align: top; }
    .table-items { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
    .table-items th { background-color: #F8F9FA; color: #1F1F1F; font-size: 12px; font-weight: 700; text-transform: uppercase; padding: 12px; text-align: left; }
    .table-items td { padding: 15px 12px; border-bottom: 1px solid #EEEEEE; font-size: 14px; color: #333333; }
    .total-row td { font-weight: 800; font-size: 16px; color: #EF7F1F; border-bottom: none; padding-top: 20px; }
    .success-alert { background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 16px; padding: 20px; text-align: center; color: #065F46; font-size: 14px; font-weight: 600; margin-bottom: 30px; }
    .footer { padding: 30px 20px; background-color: #F8F9FA; text-align: center; border-top: 1px solid #EEEEEE; }
    .footer-text { font-size: 12px; color: #999999; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="email-container">
    <div class="brand-header" style="overflow: hidden;">
      <img src="https://lh3.googleusercontent.com/d/1z4l9PuXoNFcJfwLTZn-D7zWq4ALjjxcf" alt="GenKiddo" style="height: 55px; border: 0; float: left; display: block;" />
      <span class="invoice-title" style="margin-top: 15px;">Kuitansi</span>
    </div>
    <div class="email-body">
      <div class="success-alert">
        Pembayaran Anda Berhasil Diverifikasi!
      </div>
      
      <div class="invoice-details">
        <div class="invoice-col">
          <strong>Ditagih untuk:</strong><br>
          {parent_name}<br>
          {parent_email}
        </div>
        <div class="invoice-col" style="text-align: right;">
          <strong>No. Transaksi:</strong> #{order_id}<br>
          <strong>Tanggal:</strong> {payment_date}<br>
          <strong>Metode:</strong> {payment_method}
        </div>
      </div>

      <table class="table-items">
        <thead>
          <tr>
            <th>Deskripsi Kelas</th>
            <th style="text-align: right;">Total Harga</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              <strong>{class_name}</strong><br>
              <span style="font-size: 11px; color: #888;">Kelas untuk anak: {student_name}</span>
            </td>
            <td style="text-align: right; font-weight: 700;">{subtotal}</td>
          </tr>
          {discount_rows}
          <tr class="total-row">
            <td style="text-align: right;">Total Dibayar:</td>
            <td style="text-align: right; padding-top: 20px;">{price}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="footer">
      <p class="footer-text">
        © 2026 GenKiddo Academy. Semua Hak Dilindungi.<br>
        Jl. Teknik Kimia Keputih, Sukolilo Surabaya, Jawa Timur 60111.
      </p>
    </div>
  </div>
</body>
</html>
"""
