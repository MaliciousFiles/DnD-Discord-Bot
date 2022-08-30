$exe_dir = "$Env:ProgramFiles\CafeiSMP Bot"

mkdir $exe_dir
python setup.py py2exe -d $exe_dir
mv -Force $exe_dir\main.exe "$exe_dir\CafeiSMP Bot.exe"
cp icon.png $exe_dir

$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$Env:ProgramData\Microsoft\Windows\Start Menu\Programs\CafeiSMP Bot.lnk")
$Shortcut.TargetPath = "$exe_dir\CafeiSMP Bot.exe"
$Shortcut.Save()