use std::{
    path::PathBuf,
    process::{Child, Command},
    sync::Mutex,
};

use tauri::{Manager, RunEvent};

struct LocalApi(Mutex<Option<Child>>);

fn api_launcher(app: &tauri::AppHandle) -> PathBuf {
    let resource_path = app
        .path()
        .resource_dir()
        .expect("unable to resolve app resource directory")
        .join("run_local_api.sh");
    if resource_path.exists() {
        return resource_path;
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../run_local_api.sh")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let launcher = api_launcher(app.handle());
            let working_directory = launcher
                .parent()
                .expect("local API launcher has no parent directory");
            let child = Command::new(&launcher)
                .current_dir(working_directory)
                .spawn()
                .map_err(|error| format!("failed to start local analysis API: {error}"))?;
            app.manage(LocalApi(Mutex::new(Some(child))));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Gaga Korean");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = app_handle.try_state::<LocalApi>() {
                if let Ok(mut process) = state.0.lock() {
                    if let Some(mut child) = process.take() {
                        let _ = child.kill();
                    }
                }
            }
        }
    });
}
