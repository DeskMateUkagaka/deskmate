mod commands;
mod ocs;
mod openclaw;
mod quake_terminal;
mod settings;
mod skin;

use std::sync::{Arc, Mutex};

use tauri::{Emitter, Manager};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;

use commands::chat::GatewayState;
use commands::proactive::ProactiveState;

fn toggle_main_window(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        if win.is_visible().unwrap_or(false) {
            let _ = win.hide();
        } else {
            let _ = win.show();
            let _ = win.set_focus();
        }
    }
}

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

            // Initialize HTTP client for OCS API
            app.manage(reqwest::Client::new());

            // Initialize quake terminal state
            app.manage(Arc::new(Mutex::new(quake_terminal::QuakeTerminalState::new())));

            // Register global hotkey for quake terminal
            // All errors are caught and logged — never crash the app on bad hotkey config.
            'quake: {
                let qt_config = {
                    let s = app.state::<std::sync::Mutex<crate::settings::Settings>>();
                    let guard = s.lock().unwrap();
                    guard.quake_terminal.clone()
                };

                if !qt_config.enabled {
                    break 'quake;
                }

                if let Err(e) = app.handle().plugin(
                    tauri_plugin_global_shortcut::Builder::new()
                        .with_handler(move |_app, _shortcut, event| {
                            use tauri_plugin_global_shortcut::ShortcutState;
                            if event.state == ShortcutState::Pressed {
                                let qt_state = _app.state::<Arc<Mutex<quake_terminal::QuakeTerminalState>>>();
                                let settings = _app.state::<std::sync::Mutex<crate::settings::Settings>>();
                                let config = settings.lock().unwrap().quake_terminal.clone();
                                let mut state = qt_state.lock().unwrap();
                                if let Err(e) = quake_terminal::toggle::toggle(&mut state, &config, _app) {
                                    log::error!("Quake terminal toggle failed: {e}");
                                    let _ = _app.emit("quake-terminal-error", e);
                                }
                            }
                        })
                        .build(),
                ) {
                    log::error!("Failed to register global shortcut plugin: {e}");
                    break 'quake;
                }

                use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};
                let shortcut: Shortcut = match qt_config.hotkey.parse() {
                    Ok(s) => s,
                    Err(e) => {
                        log::error!("Invalid quake terminal hotkey '{}': {e}", qt_config.hotkey);
                        break 'quake;
                    }
                };
                if let Err(e) = app.handle().global_shortcut().register(shortcut) {
                    log::error!("Failed to register hotkey '{}': {e}", qt_config.hotkey);
                    break 'quake;
                }
                log::info!("Registered quake terminal hotkey: {}", qt_config.hotkey);
            }

            // System tray
            // On Linux (libappindicator), left/right click can't be distinguished —
            // any click shows the menu. Add "Show / Hide" as first item for Linux.
            // On macOS/Windows, left click toggles via on_tray_icon_event.
            let handle = app.handle();
            let toggle_item = MenuItem::with_id(handle, "toggle", "Show / Hide", true, None::<&str>)?;
            let sep0 = PredefinedMenuItem::separator(handle)?;
            let change_skin = MenuItem::with_id(handle, "change-skin", "Change Skin", true, None::<&str>)?;
            let get_skins = MenuItem::with_id(handle, "get-skins", "Get Skins", true, None::<&str>)?;
            let sep1 = PredefinedMenuItem::separator(handle)?;
            let settings_item = MenuItem::with_id(handle, "settings", "Settings", true, None::<&str>)?;
            let sep2 = PredefinedMenuItem::separator(handle)?;
            let exit_item = MenuItem::with_id(handle, "exit", "Exit", true, None::<&str>)?;
            let tray_menu = Menu::with_items(handle, &[&toggle_item, &sep0, &change_skin, &get_skins, &sep1, &settings_item, &sep2, &exit_item])?;

            TrayIconBuilder::new()
                .icon(handle.default_window_icon().unwrap().clone())
                .tooltip("DeskMate")
                .menu(&tray_menu)
                .show_menu_on_left_click(false)
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::Click {
                        button: tauri::tray::MouseButton::Left,
                        button_state: tauri::tray::MouseButtonState::Up,
                        ..
                    } = event
                    {
                        toggle_main_window(tray.app_handle());
                    }
                })
                .on_menu_event(|app, event| {
                    match event.id.as_ref() {
                        "toggle" => {
                            toggle_main_window(app);
                        }
                        "change-skin" => {
                            if let Some(win) = app.get_webview_window("skin-picker") {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                        "get-skins" => {
                            if let Some(win) = app.get_webview_window("get-skins") {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                        "settings" => {
                            if let Some(win) = app.get_webview_window("settings") {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                        "exit" => {
                            // Kill quake terminal process before exiting
                            if let Ok(mut qt) = app.state::<Arc<Mutex<quake_terminal::QuakeTerminalState>>>().lock() {
                                if let Some(ref mut child) = qt.process {
                                    let _ = child.kill();
                                    log::info!("Killed quake terminal process on exit");
                                }
                            }
                            // Save ghost window position before exiting
                            if let Some(win) = app.get_webview_window("main") {
                                if let Ok(pos) = win.outer_position() {
                                    if let Ok(mut s) = app.state::<std::sync::Mutex<crate::settings::Settings>>().lock() {
                                        s.ghost_x = pos.x as f64;
                                        s.ghost_y = pos.y as f64;
                                        s.save(&app);
                                    }
                                }
                            }
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .build(handle)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::ghost::get_ghost_position,
            commands::ghost::set_ghost_position,
            commands::ghost::debug_log,
            commands::ghost::exit_app,
            commands::skin::list_skins,
            commands::skin::get_current_skin,
            commands::skin::switch_skin,
            commands::skin::get_emotion_image,
            commands::skin::reload_skins,
            commands::skin::get_idle_animation_path,
            commands::settings::get_settings,
            commands::settings::reload_settings,
            commands::settings::update_settings,
            commands::chat::connect_gateway,
            commands::chat::get_connection_status,
            commands::chat::list_sessions,
            commands::chat::chat_send,
            commands::chat::chat_abort,
            commands::proactive::start_proactive,
            commands::proactive::stop_proactive,
            commands::window::move_window,
            commands::window::get_window_position,
            commands::window::uses_compositor_ipc,
            commands::e2e::e2e_inject_event,
            commands::ocs::ocs_browse,
            commands::ocs::ocs_download_skin,
            commands::ocs::get_installed_skin_ids,
            commands::quake_terminal::toggle_quake_terminal,
            commands::quake_terminal::get_quake_terminal_status,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
