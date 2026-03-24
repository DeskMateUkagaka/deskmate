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

            // On Sway/Hyprland, showing a hidden window resets its position.
            // Move it back to the saved position from settings.
            let handle = app.clone();
            tauri::async_runtime::spawn(async move {
                let (x, y) = {
                    let s = handle.state::<std::sync::Mutex<settings::Settings>>();
                    let guard = s.lock().unwrap();
                    (guard.ghost_x as i32, guard.ghost_y as i32)
                };
                commands::window::move_window("deskmate-ghost".to_string(), x, y).await;
            });
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

            // Initialize skin manager with persisted skin choice
            let initial_skin_id = {
                let s = app.state::<std::sync::Mutex<settings::Settings>>();
                let guard = s.lock().unwrap();
                guard.current_skin_id.clone()
            };
            let skin_manager = skin::SkinManager::new(&app.handle(), &initial_skin_id);
            app.manage(std::sync::Mutex::new(skin_manager));

            // Initialize gateway state (disconnected until connect_gateway is called)
            app.manage(Arc::new(Mutex::new(GatewayState::new())));

            // Initialize proactive dialogue state
            app.manage(Arc::new(Mutex::new(ProactiveState::new())));

            // Initialize HTTP client for OCS API
            app.manage(reqwest::Client::new());

            // Initialize quake terminal state
            app.manage(Arc::new(Mutex::new(quake_terminal::QuakeTerminalState::new())));

            // Register global hotkeys.
            // All errors are caught and logged — never crash the app on bad hotkey config.
            {
                let (qt_config, ghost_hotkey) = {
                    let s = app.state::<std::sync::Mutex<crate::settings::Settings>>();
                    let guard = s.lock().unwrap();
                    (guard.quake_terminal.clone(), guard.ghost_toggle_hotkey.clone())
                };

                use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

                // Parse shortcuts up front so the handler can compare by value.
                let quake_shortcut: Option<Shortcut> = if qt_config.enabled {
                    match qt_config.hotkey.parse() {
                        Ok(s) => Some(s),
                        Err(e) => {
                            log::error!("Invalid quake terminal hotkey '{}': {e}", qt_config.hotkey);
                            None
                        }
                    }
                } else {
                    None
                };
                let ghost_shortcut: Option<Shortcut> = match ghost_hotkey.parse() {
                    Ok(s) => Some(s),
                    Err(e) => {
                        log::error!("Invalid ghost toggle hotkey '{}': {e}", ghost_hotkey);
                        None
                    }
                };

                let qs_for_handler = quake_shortcut;
                let gs_for_handler = ghost_shortcut;

                if let Err(e) = app.handle().plugin(
                    tauri_plugin_global_shortcut::Builder::new()
                        .with_handler(move |_app, shortcut, event| {
                            use tauri_plugin_global_shortcut::ShortcutState;
                            if event.state != ShortcutState::Pressed {
                                return;
                            }
                            if qs_for_handler.as_ref() == Some(shortcut) {
                                let qt_state = _app.state::<Arc<Mutex<quake_terminal::QuakeTerminalState>>>();
                                let settings = _app.state::<std::sync::Mutex<crate::settings::Settings>>();
                                let config = settings.lock().unwrap().quake_terminal.clone();
                                let mut state = qt_state.lock().unwrap();
                                if let Err(e) = quake_terminal::toggle::toggle(&mut state, &config, _app) {
                                    log::error!("Quake terminal toggle failed: {e}");
                                    let _ = _app.emit("quake-terminal-error", e);
                                }
                            } else if gs_for_handler.as_ref() == Some(shortcut) {
                                toggle_main_window(_app);
                            }
                        })
                        .build(),
                ) {
                    log::error!("Failed to register global shortcut plugin: {e}");
                } else {
                    // Register individual shortcuts
                    if let Some(qs) = quake_shortcut {
                        if let Err(e) = app.handle().global_shortcut().register(qs) {
                            log::error!("Failed to register quake hotkey '{}': {e}", qt_config.hotkey);
                        } else {
                            log::info!("Registered quake terminal hotkey: {}", qt_config.hotkey);
                        }
                    }
                    if let Some(gs) = ghost_shortcut {
                        if let Err(e) = app.handle().global_shortcut().register(gs) {
                            log::error!("Failed to register ghost toggle hotkey '{}': {e}", ghost_hotkey);
                        } else {
                            log::info!("Registered ghost toggle hotkey: {}", ghost_hotkey);
                        }
                    }
                }
            }

            // Signal handlers for Wayland compositors.
            // Global hotkeys don't work on Wayland, so users bind keys in their
            // compositor config to send signals instead:
            //   SIGUSR1 → toggle quake terminal:  `pkill -USR1 -x deskmate`
            //   SIGUSR2 → toggle ghost:           `pkill -USR2 -x deskmate`
            #[cfg(unix)]
            {
                use std::sync::atomic::{AtomicBool, Ordering};
                static SIGUSR1: AtomicBool = AtomicBool::new(false);
                static SIGUSR2: AtomicBool = AtomicBool::new(false);

                extern "C" fn sigusr1_handler(_: libc::c_int) {
                    SIGUSR1.store(true, Ordering::SeqCst);
                }
                extern "C" fn sigusr2_handler(_: libc::c_int) {
                    SIGUSR2.store(true, Ordering::SeqCst);
                }
                // SAFETY: handlers only set atomic bools — async-signal-safe.
                unsafe {
                    libc::signal(libc::SIGUSR1, sigusr1_handler as libc::sighandler_t);
                    libc::signal(libc::SIGUSR2, sigusr2_handler as libc::sighandler_t);
                }

                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    loop {
                        std::thread::sleep(std::time::Duration::from_millis(100));
                        if SIGUSR1.swap(false, Ordering::SeqCst) {
                            log::info!("SIGUSR1 received — toggling quake terminal");
                            let qt_state = handle.state::<Arc<Mutex<quake_terminal::QuakeTerminalState>>>();
                            let settings = handle.state::<std::sync::Mutex<crate::settings::Settings>>();
                            let config = settings.lock().unwrap().quake_terminal.clone();
                            let mut state = qt_state.lock().unwrap();
                            if let Err(e) = quake_terminal::toggle::toggle(&mut state, &config, &handle) {
                                log::error!("Quake terminal toggle (SIGUSR1) failed: {e}");
                            }
                        }
                        if SIGUSR2.swap(false, Ordering::SeqCst) {
                            log::info!("SIGUSR2 received — toggling ghost");
                            toggle_main_window(&handle);
                        }
                    }
                });
                log::info!("Signal handlers registered: SIGUSR1 (quake), SIGUSR2 (ghost)");
            }

            // System tray
            // On Linux (libappindicator), left/right click can't be distinguished —
            // any click shows the menu. Add "Show / Hide" as first item for Linux.
            // On macOS/Windows, left click toggles via on_tray_icon_event.
            let handle = app.handle();
            let toggle_item = MenuItem::with_id(handle, "toggle", "Show / Hide", true, None::<&str>)?;
            let sep0 = PredefinedMenuItem::separator(handle)?;
            let change_skin = MenuItem::with_id(handle, "change-skin", "Change Skin", true, None::<&str>)?;
            let reload_item = MenuItem::with_id(handle, "reload-settings", "Reload Settings", true, None::<&str>)?;
            let get_skins = MenuItem::with_id(handle, "get-skins", "Get Skins", true, None::<&str>)?;
            let sep1 = PredefinedMenuItem::separator(handle)?;
            let history_item = MenuItem::with_id(handle, "conversation-history", "Conversation History", true, None::<&str>)?;
            let settings_item = MenuItem::with_id(handle, "settings", "Settings", true, None::<&str>)?;
            let sep2 = PredefinedMenuItem::separator(handle)?;
            let exit_item = MenuItem::with_id(handle, "exit", "Exit", true, None::<&str>)?;
            let tray_menu = Menu::with_items(handle, &[&toggle_item, &sep0, &change_skin, &reload_item, &get_skins, &sep1, &history_item, &settings_item, &sep2, &exit_item])?;

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
                    // Forward all tray menu actions to the frontend as events.
                    // The frontend shares action handling with the ghost context menu.
                    let action = event.id.as_ref().to_string();
                    let _ = app.emit("menu-action", &action);
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
            commands::skin::get_emotion_images,
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
