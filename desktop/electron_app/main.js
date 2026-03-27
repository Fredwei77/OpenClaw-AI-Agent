const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let mainWindow;
let pyProc = null;

const createPyProc = () => {
  let scriptPath = app.isPackaged 
    ? path.join(process.resourcesPath, 'backend', 'main.py') 
    : path.join(__dirname, '../../backend/main.py');
  
  let cwd = app.isPackaged 
    ? process.resourcesPath 
    : path.join(__dirname, '../../backend');

  let pythonExecutable = 'python';
  
  // Attempt to use the virtual environment python if available
  if (!app.isPackaged) {
    console.log("__dirname is:", __dirname);
    console.log("process.cwd() is:", process.cwd());
    const venvWin1 = path.join(__dirname, '../../.venv/Scripts/python.exe');
    const venvWin2 = path.join(process.cwd(), '../../.venv/Scripts/python.exe');
    const venvWin3 = path.join(process.cwd(), '../.venv/Scripts/python.exe');
    const venvMac = path.join(__dirname, '../../.venv/bin/python');
    
    if (fs.existsSync(venvWin1)) {
      pythonExecutable = venvWin1;
    } else if (fs.existsSync(venvWin2)) {
      pythonExecutable = venvWin2;
    } else if (fs.existsSync(venvWin3)) {
      pythonExecutable = venvWin3;
    } else if (fs.existsSync(venvMac)) {
      pythonExecutable = venvMac;
    }
    fs.writeFileSync('python_path_debug.txt', `Resolved Python Executable: ${pythonExecutable}\n__dirname: ${__dirname}\ncwd: ${process.cwd()}`);
  }

  pyProc = spawn(pythonExecutable, [scriptPath], {cwd: cwd});

  if (pyProc != null) {
      console.log(`FastAPI server spawned successfully using ${pythonExecutable}. CWD: ` + cwd);
      pyProc.stdout.on('data', function(data) {
          console.log(`[python] ${data.toString()}`);
      });
      pyProc.stderr.on('data', function(data) {
          console.log(`[python err] ${data.toString()}`);
      });
  }
}

const exitPyProc = () => {
  if (pyProc) {
      pyProc.kill();
      pyProc = null;
      console.log('FastAPI server killed.');
  }
}

app.on('ready', () => {
  createPyProc();
  
  mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      autoHideMenuBar: true,
      webPreferences: {
          nodeIntegration: true,
          contextIsolation: false
      }
  });

  const indexPath = app.isPackaged 
    ? path.join(process.resourcesPath, 'www', 'index.html') 
    : path.join(__dirname, '../../frontend/dist/index.html');
  
  console.log('Loading UI from:', indexPath);

  // Give Python backend 2 seconds to initialize its Uvicorn server before loading the UI
  // The UI calls localhost:8000 on load or user action
  setTimeout(() => {
     mainWindow.loadFile(indexPath);
  }, 2000);

  mainWindow.on('closed', () => {
      mainWindow = null;
  });
});

app.on('will-quit', exitPyProc);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
