# Long-lived Windows input helper: reads one JSON action per stdin line, writes one JSON result per line.
# Started and killed by computer-control.js; exits when stdin closes. Coordinates are physical pixels.
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @"
using System; using System.Collections.Generic; using System.Runtime.InteropServices; using System.Threading;
public static class SiroInput {
  [StructLayout(LayoutKind.Sequential)] struct MOUSEINPUT { public int dx, dy; public uint data, flags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Sequential)] struct KEYBDINPUT { public ushort vk, scan; public uint flags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Explicit)] struct U { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
  [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public U u; }
  [DllImport("user32.dll", SetLastError=true)] static extern uint SendInput(uint n, INPUT[] i, int size);
  [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] static extern uint MapVirtualKey(uint code, uint type);
  [DllImport("user32.dll")] static extern short VkKeyScanEx(char c, IntPtr hkl);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr LoadKeyboardLayout(string id, uint flags);
  [DllImport("user32.dll")] static extern IntPtr GetKeyboardLayout(uint thread);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  static readonly ushort[] Extended = { 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C };
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
    bool right = button == "right";
    Mouse(right ? 0x0008u : 0x0002u, 0); Thread.Sleep(40); Mouse(right ? 0x0010u : 0x0004u, 0);
  }
  public static void Wheel(int notches) { Mouse(0x0800, unchecked((uint)(notches * 120))); }
  // Hardware-style scancode events so games (DirectInput / raw input) see them, not only text boxes.
  static void Key(ushort vk, bool up) {
    var i = new INPUT(); i.type = 1; i.u.ki.scan = (ushort)MapVirtualKey(vk, 0);
    uint f = 8; if (Array.IndexOf(Extended, vk) >= 0) f |= 1; if (up) f |= 2; i.u.ki.flags = f; Send(i);
  }
  public static void Combo(ushort[] vks, int holdMs) {
    int pressed = 0;
    try { foreach (var vk in vks) { Key(vk, false); pressed++; } Thread.Sleep(holdMs); }
    finally { for (int n = pressed - 1; n >= 0; n--) Key(vks[n], true); }
  }
  // IMEs (Japanese/Zhuyin) turn plain letter keys into composition, so type under the US layout and restore it.
  public static void Text(string text) {
    IntPtr hwnd = GetForegroundWindow(); uint pid; uint tid = GetWindowThreadProcessId(hwnd, out pid);
    IntPtr original = GetKeyboardLayout(tid), us = LoadKeyboardLayout("00000409", 0);
    bool switched = ((long)original & 0xFFFF) != 0x0409;
    if (switched) { PostMessage(hwnd, 0x50, IntPtr.Zero, us); Thread.Sleep(200); }
    try { TypeChars(text, us); }
    finally { if (switched) PostMessage(hwnd, 0x50, IntPtr.Zero, original); }
  }
  static void TypeChars(string text, IntPtr us) {
    foreach (char c in text) {
      short r = c < 128 ? VkKeyScanEx(c, us) : (short)-1;
      if (r != -1) {
        var keys = new List<ushort>(); int sh = (r >> 8) & 0xFF;
        if ((sh & 1) != 0) keys.Add(0x10); if ((sh & 2) != 0) keys.Add(0x11); if ((sh & 4) != 0) keys.Add(0x12);
        keys.Add((ushort)(r & 0xFF)); Combo(keys.ToArray(), 12);
      } else {
        var d = new INPUT(); d.type = 1; d.u.ki.scan = c; d.u.ki.flags = 4; Send(d);
        var u = new INPUT(); u.type = 1; u.u.ki.scan = c; u.u.ki.flags = 6; Send(u);
      }
      Thread.Sleep(8);
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
      'key'    { $hold = 45; if ($a.hold_ms -gt 0) { $hold = [int]$a.hold_ms }
                 [SiroInput]::Combo([uint16[]]@(([string]$a.key).ToLower().Split('+') | ForEach-Object { KeyCode $_ }), $hold) }
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
