# Long-lived Windows input helper: reads one JSON action per stdin line, writes one JSON result per line.
# Started and killed by computer-control.js; exits when stdin closes. Coordinates are physical pixels.
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class SiroInput {
  [StructLayout(LayoutKind.Sequential)] struct MOUSEINPUT { public int dx, dy; public uint data, flags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Sequential)] struct KEYBDINPUT { public ushort vk, scan; public uint flags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Explicit)] struct U { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
  [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public U u; }
  [DllImport("user32.dll", SetLastError=true)] static extern uint SendInput(uint n, INPUT[] i, int size);
  [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int l, t, r, b; }
  public static void Init() { SetProcessDPIAware(); }
  public static object[] Foreground() {
    IntPtr h = GetForegroundWindow();
    if (h == IntPtr.Zero) return null;
    var sb = new System.Text.StringBuilder(256); GetWindowText(h, sb, 256);
    RECT r; GetWindowRect(h, out r); uint pid; GetWindowThreadProcessId(h, out pid);
    return new object[] { sb.ToString(), (int)pid, r.l, r.t, r.r - r.l, r.b - r.t };
  }
  static void Send(INPUT i) {
    if (SendInput(1, new INPUT[] { i }, Marshal.SizeOf(typeof(INPUT))) != 1) throw new Exception("SendInput blocked (code " + Marshal.GetLastWin32Error() + ")");
  }
  static void Mouse(uint flags, uint data) { var i = new INPUT(); i.type = 0; i.u.mi.flags = flags; i.u.mi.data = data; Send(i); }
  public static void Move(int x, int y) { if (!SetCursorPos(x, y)) throw new Exception("SetCursorPos failed"); }
  public static void Click(string button) {
    if (button == "right") { Mouse(0x0008, 0); Mouse(0x0010, 0); } else { Mouse(0x0002, 0); Mouse(0x0004, 0); }
  }
  public static void Wheel(int notches) { Mouse(0x0800, unchecked((uint)(notches * 120))); }
  static void Key(ushort vk, bool up) { var i = new INPUT(); i.type = 1; i.u.ki.vk = vk; i.u.ki.flags = up ? 2u : 0u; Send(i); }
  public static void Combo(ushort[] vks) {
    int pressed = 0;
    try { foreach (var vk in vks) { Key(vk, false); pressed++; } }
    finally { for (int n = pressed - 1; n >= 0; n--) Key(vks[n], true); }
  }
  public static void Text(string text) {
    foreach (char c in text) {
      var d = new INPUT(); d.type = 1; d.u.ki.scan = c; d.u.ki.flags = 4; Send(d);
      var u = new INPUT(); u.type = 1; u.u.ki.scan = c; u.u.ki.flags = 6; Send(u);
    }
  }
}
"@
[SiroInput]::Init()
$vk = @{ ctrl=0x11; shift=0x10; alt=0x12; win=0x5B; enter=0x0D; escape=0x1B; space=0x20; tab=0x09; backspace=0x08; delete=0x2E;
  left=0x25; up=0x26; right=0x27; down=0x28; home=0x24; end=0x23; pageup=0x21; pagedown=0x22 }
for ($n = 1; $n -le 12; $n++) { $vk["f$n"] = 0x6F + $n }
function KeyCode([string]$name) {
  if ($vk.ContainsKey($name)) { return [uint16]$vk[$name] }
  if ($name -match '^[a-z0-9]$') { return [uint16][int][char]$name.ToUpper() }
  throw "unknown key '$name'"
}
Add-Type -AssemblyName UIAutomationClient
function Test-SecretFocus {
  try { return [bool][System.Windows.Automation.AutomationElement]::FocusedElement.Current.IsPassword } catch { return $false }
}
while (($line = [Console]::In.ReadLine()) -ne $null) {
  $id = $null; $reply = $null
  try {
    $a = $line | ConvertFrom-Json
    $id = $a.id
    switch ($a.kind) {
      'move'   { [SiroInput]::Move([int]$a.x, [int]$a.y) }
      'click'  { [SiroInput]::Move([int]$a.x, [int]$a.y); [SiroInput]::Click([string]$a.button) }
      'scroll' { [SiroInput]::Wheel([int]$a.amount) }
      'key'    { [SiroInput]::Combo([uint16[]]@(([string]$a.key).ToLower().Split('+') | ForEach-Object { KeyCode $_ })) }
      'type'   { [SiroInput]::Text([string]$a.text) }
      'window' { $w = [SiroInput]::Foreground()
                 if ($null -eq $w) { throw 'no foreground window' }
                 $proc = (Get-Process -Id $w[1] -ErrorAction Stop).ProcessName + '.exe'
                 $reply = @{ id = $id; ok = $true; title = $w[0]; process = $proc; rect = @($w[2], $w[3], $w[4], $w[5]); secret = (Test-SecretFocus) } }
      default  { throw "kind not allowed: $($a.kind)" }
    }
    if ($null -eq $reply) { $reply = @{ id = $id; ok = $true } }
    Write-Output ($reply | ConvertTo-Json -Compress)
  } catch {
    Write-Output (@{ id = $id; ok = $false; error = [string]$_.Exception.Message } | ConvertTo-Json -Compress)
  }
}
