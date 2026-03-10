mod commands;
mod openclaw;
mod settings;
mod skin;

use std::sync::{Arc, Mutex};

use tauri::Manager;

use commands::chat::GatewayState;
use commands::proactive::ProactiveState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::default().build())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .targets([
                            tauri_plugin_log::Target::new(
                                tauri_plugin_log::TargetKind::Stdout,
                            ),
                        ])
                        .build(),
                )?;
            }

            // Initialize settings with defaults
            let app_handle = app.handle().clone();
            let settings = settings::Settings::load(&app_handle);
            app.manage(std::sync::Mutex::new(settings));

            // Initialize skin manager
            let skin_manager = skin::SkinManager::new(&app.handle());
            app.manage(std::sync::Mutex::new(skin_manager));

            // Initialize gateway state (disconnected until connect_gateway is called)
            app.manage(Arc::new(Mutex::new(GatewayState::new())));

            // Initialize proactive dialogue state
            app.manage(Arc::new(Mutex::new(ProactiveState::new())));

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::ghost::get_ghost_position,
            commands::ghost::set_ghost_position,
            commands::ghost::debug_log,
            commands::skin::list_skins,
            commands::skin::get_current_skin,
            commands::skin::switch_skin,
            commands::skin::get_expression_image,
            commands::settings::get_settings,
            commands::settings::update_settings,
            commands::chat::connect_gateway,
            commands::chat::get_connection_status,
            commands::chat::list_sessions,
            commands::chat::chat_send,
            commands::chat::chat_abort,
            commands::proactive::start_proactive,
            commands::proactive::stop_proactive,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
