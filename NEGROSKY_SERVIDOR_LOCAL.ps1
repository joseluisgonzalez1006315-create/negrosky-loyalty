Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$LogPath = Join-Path $Root 'servidor_local.log'
$Port = 8030
$ServerProcess = $null

$form = New-Object System.Windows.Forms.Form
$form.Text = 'NEGROSKY LOYALTY - Servidor local'
$form.Size = New-Object System.Drawing.Size(760, 560)
$form.StartPosition = 'CenterScreen'
$form.BackColor = [System.Drawing.Color]::FromArgb(24, 27, 36)
$form.ForeColor = [System.Drawing.Color]::White
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)

$title = New-Object System.Windows.Forms.Label
$title.Text = 'NEGROSKY LOYALTY'
$title.Font = New-Object System.Drawing.Font('Segoe UI', 20, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(190, 150, 255)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(24, 20)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = 'Servidor local con PostgreSQL'
$subtitle.AutoSize = $true
$subtitle.Location = New-Object System.Drawing.Point(28, 60)
$form.Controls.Add($subtitle)

$label = New-Object System.Windows.Forms.Label
$label.Text = 'Contraseña local de PostgreSQL:'
$label.AutoSize = $true
$label.Location = New-Object System.Drawing.Point(28, 98)
$form.Controls.Add($label)

$password = New-Object System.Windows.Forms.TextBox
$password.Location = New-Object System.Drawing.Point(28, 124)
$password.Size = New-Object System.Drawing.Size(340, 30)
$password.UseSystemPasswordChar = $true
$password.BackColor = [System.Drawing.Color]::FromArgb(38, 42, 54)
$password.ForeColor = [System.Drawing.Color]::White
$form.Controls.Add($password)

$status = New-Object System.Windows.Forms.Label
$status.Text = 'Estado: detenido'
$status.AutoSize = $true
$status.Location = New-Object System.Drawing.Point(400, 130)
$status.ForeColor = [System.Drawing.Color]::Gold
$form.Controls.Add($status)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ScrollBars = 'Vertical'
$logBox.ReadOnly = $true
$logBox.BackColor = [System.Drawing.Color]::FromArgb(14, 16, 22)
$logBox.ForeColor = [System.Drawing.Color]::FromArgb(220, 220, 220)
$logBox.Location = New-Object System.Drawing.Point(28, 220)
$logBox.Size = New-Object System.Drawing.Size(688, 250)
$logBox.Font = New-Object System.Drawing.Font('Consolas', 9)
$form.Controls.Add($logBox)

function Add-Log([string]$Text) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Text"
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    $logBox.AppendText($line + [Environment]::NewLine)
}

function Stop-Server {
    if ($script:ServerProcess -and -not $script:ServerProcess.HasExited) {
        try { $script:ServerProcess.Kill() } catch {}
        try { $script:ServerProcess.WaitForExit(3000) } catch {}
        Add-Log 'Servidor detenido.'
    }
    $script:ServerProcess = $null
    $status.Text = 'Estado: detenido'
    $status.ForeColor = [System.Drawing.Color]::Gold
}

$start = New-Object System.Windows.Forms.Button
$start.Text = 'Iniciar servidor'
$start.Location = New-Object System.Drawing.Point(28, 170)
$start.Size = New-Object System.Drawing.Size(150, 36)
$start.BackColor = [System.Drawing.Color]::FromArgb(80, 170, 105)
$start.ForeColor = [System.Drawing.Color]::White
$start.FlatStyle = 'Flat'
$form.Controls.Add($start)

$stop = New-Object System.Windows.Forms.Button
$stop.Text = 'Detener servidor'
$stop.Location = New-Object System.Drawing.Point(190, 170)
$stop.Size = New-Object System.Drawing.Size(150, 36)
$stop.BackColor = [System.Drawing.Color]::FromArgb(175, 70, 70)
$stop.ForeColor = [System.Drawing.Color]::White
$stop.FlatStyle = 'Flat'
$form.Controls.Add($stop)

$open = New-Object System.Windows.Forms.Button
$open.Text = 'Abrir Loyalty'
$open.Location = New-Object System.Drawing.Point(352, 170)
$open.Size = New-Object System.Drawing.Size(150, 36)
$open.BackColor = [System.Drawing.Color]::FromArgb(105, 85, 185)
$open.ForeColor = [System.Drawing.Color]::White
$open.FlatStyle = 'Flat'
$form.Controls.Add($open)

$clear = New-Object System.Windows.Forms.Button
$clear.Text = 'Limpiar registro'
$clear.Location = New-Object System.Drawing.Point(514, 170)
$clear.Size = New-Object System.Drawing.Size(150, 36)
$clear.BackColor = [System.Drawing.Color]::FromArgb(65, 70, 85)
$clear.ForeColor = [System.Drawing.Color]::White
$clear.FlatStyle = 'Flat'
$form.Controls.Add($clear)

$start.Add_Click({
    try {
        if (-not (Test-Path $Python)) { throw "No se encontró .venv. Ejecuta primero la instalación del proyecto." }
        if ($script:ServerProcess -and -not $script:ServerProcess.HasExited) { Add-Log 'El servidor ya está iniciado.'; return }
        if ([string]::IsNullOrWhiteSpace($password.Text)) { [System.Windows.Forms.MessageBox]::Show('Escribe la contraseña local de PostgreSQL.'); return }
        $env:PGPASSWORD = $password.Text
        $env:DATABASE_URL = 'postgresql://postgres@localhost:5432/negrosky_loyalty'
        $env:SUPABASE_DB_URL = $null
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Python
        $psi.Arguments = '-m uvicorn app.main:app --host 0.0.0.0 --port 8030'
        $psi.WorkingDirectory = $Root
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $script:ServerProcess = New-Object System.Diagnostics.Process
        $script:ServerProcess.StartInfo = $psi
        $script:ServerProcess.add_OutputDataReceived({ param($s,$e) if ($e.Data) { $form.BeginInvoke([Action]{ Add-Log $e.Data }) } })
        $script:ServerProcess.add_ErrorDataReceived({ param($s,$e) if ($e.Data) { $form.BeginInvoke([Action]{ Add-Log $e.Data }) } })
        [void]$script:ServerProcess.Start()
        $script:ServerProcess.BeginOutputReadLine()
        $script:ServerProcess.BeginErrorReadLine()
        $status.Text = 'Estado: iniciando'
        $status.ForeColor = [System.Drawing.Color]::LightGreen
        Add-Log 'Iniciando servidor en http://localhost:8030'
    } catch { Add-Log ('ERROR: ' + $_.Exception.Message); [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Negrosky') }
})

$stop.Add_Click({ Stop-Server })
$open.Add_Click({ Start-Process 'http://localhost:8030' })
$clear.Add_Click({ $logBox.Clear(); Set-Content -LiteralPath $LogPath -Value '' -Encoding UTF8 })
$form.Add_FormClosing({ Stop-Server })

if (Test-Path $LogPath) { Get-Content $LogPath -Tail 30 | ForEach-Object { $logBox.AppendText($_ + [Environment]::NewLine) } }
[void]$form.ShowDialog()
