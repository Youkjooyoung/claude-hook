# Claude Code Stop 훅: 답변 완료 시 화면 왼쪽 아래에 알림창을 띄우고 3초 후 자동으로 닫는다.
# 디자인: 배민(baemin.md) — 민트 풀배경 + 검정 손그림 윤곽선 + 6px 스티커 그림자 + 검정 알약 버튼
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$folder = ''
try {
    $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
    if ($payload.cwd) { $folder = Split-Path -Leaf $payload.cwd }
} catch {}

$mint  = [System.Drawing.ColorTranslator]::FromHtml('#0CEFD3')   # Baemin 2.0 primary
$ink   = [System.Drawing.ColorTranslator]::FromHtml('#1B1B1B')   # fg-1 / border-strong
$sub   = [System.Drawing.ColorTranslator]::FromHtml('#3D3D3D')   # fg-2
$white = [System.Drawing.Color]::White
# 창 바깥 투명 처리용. 안티앨리어싱 가장자리가 키 색과 섞여 번지므로 윤곽선(ink)에 가까운 거의 검정을 쓴다
$key   = [System.Drawing.Color]::FromArgb(1, 1, 2)

# BM 한나/주아/도현체가 설치돼 있으면 쓰고, 없으면 맑은 고딕으로 대체
$installed = (New-Object System.Drawing.Text.InstalledFontCollection).Families.Name
$display = @('BM HANNA Pro', 'BM HANNA 11yrs', 'BM JUA', 'BM DOHYEON') | Where-Object { $installed -contains $_ } | Select-Object -First 1
if (-not $display) { $display = '맑은 고딕' }

function New-RoundPath([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $r * 2
    $p.AddArc($x, $y, $d, $d, 180, 90)
    $p.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $p.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $p.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $p.CloseFigure()
    return $p
}

$W = 190; $H = 110; $shadow = 3; $radius = 12
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Claude Code'
$form.FormBorderStyle = 'None'
$form.TopMost = $true
$form.ShowInTaskbar = $false
$form.ClientSize = New-Object System.Drawing.Size(($W + $shadow), ($H + $shadow))
# 작업표시줄을 피해 작업 영역 왼쪽 아래에서 16px 안쪽에 둔다
$area = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.StartPosition = 'Manual'
$form.Location = New-Object System.Drawing.Point(($area.Left + 16), ($area.Bottom - $form.Height - 16))
$form.BackColor = $key
$form.TransparencyKey = $key

$form.Add_Paint({
    param($s, $e)
    $g = $e.Graphics
    $g.SmoothingMode = 'AntiAlias'
    $g.TextRenderingHint = 'AntiAliasGridFit'

    # 스티커 그림자: 검정 단색을 3px 아래로 평행 이동 (블러 없음)
    $sp = New-RoundPath 2 ($shadow + 1) ($W - 4) ($H - 4) $radius
    $g.FillPath((New-Object System.Drawing.SolidBrush $ink), $sp)

    # 민트 카드 + 손그림 검정 윤곽선
    $cp = New-RoundPath 2 1 ($W - 4) ($H - 4) $radius
    $g.FillPath((New-Object System.Drawing.SolidBrush $mint), $cp)
    $g.DrawPath((New-Object System.Drawing.Pen($ink, 2)), $cp)

    # 헤드라인: 한 줄 4~7자, 2줄 라인 브레이크
    $hf = New-Object System.Drawing.Font($display, 11, [System.Drawing.FontStyle]::Bold)
    $g.DrawString("Claude 답변이`n도착했어요!", $hf, (New-Object System.Drawing.SolidBrush $ink), 14, 13)

    $mf = New-Object System.Drawing.Font('맑은 고딕', 8)
    $meta = ('{0} · {1}' -f $folder, (Get-Date -Format 'HH:mm:ss')).Trim(' ', '·')
    $g.DrawString($meta, $mf, (New-Object System.Drawing.SolidBrush $sub), 15, 56)
})

# 검정 알약 버튼 (button-primary SM)
$ok = New-Object System.Windows.Forms.Label
$ok.Text = '확인 ›'
$ok.Font = New-Object System.Drawing.Font('맑은 고딕', 8, [System.Drawing.FontStyle]::Bold)
$ok.ForeColor = $white
$ok.BackColor = $ink
$ok.TextAlign = 'MiddleCenter'
$ok.Cursor = 'Hand'
$ok.SetBounds(14, 75, 56, 20)
$bp = New-RoundPath 0 0 56 20 10
$ok.Region = New-Object System.Drawing.Region($bp)
$ok.Add_Click({ $form.Close() })
$form.Controls.Add($ok)

$form.KeyPreview = $true
$form.Add_KeyDown({ param($s, $e) if ($e.KeyCode -in 'Enter', 'Escape', 'Space') { $form.Close() } })
$form.Add_MouseDown({ $form.Close() })

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 3000
$timer.Add_Tick({ $timer.Stop(); $form.Close() })
$form.Add_Shown({ $form.Activate(); $timer.Start() })

[void]$form.ShowDialog()
$timer.Dispose()
$form.Dispose()
