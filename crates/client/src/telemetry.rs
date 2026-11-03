//! Compatibility API for a build that does not collect or transmit telemetry.
use anyhow::Result;
use clock::SystemClock;
use fs::Fs;
use futures::channel::mpsc;
use gpui::{App, Task};
use http_client::HttpClientWithUrl;
#[cfg(target_os = "macos")]
use regex::Regex;
use release_channel::ReleaseChannel;
use std::{
    path::PathBuf,
    sync::{Arc, LazyLock},
};
use telemetry_events::{AssistantEventData, EventWrapper};
use worktree::{UpdatedEntriesSet, WorktreeId};

pub struct TelemetrySubscription {
    pub historical_events: Result<HistoricalEvents>,
    pub queued_events: Vec<EventWrapper>,
    pub live_events: mpsc::UnboundedReceiver<EventWrapper>,
}

pub struct HistoricalEvents {
    pub events: Vec<EventWrapper>,
    pub parse_error_count: usize,
}

/// Retains the upstream API without retaining identifiers, events, or transports.
pub struct Telemetry;

pub static MINIDUMP_ENDPOINT: LazyLock<Option<String>> = LazyLock::new(|| None);

pub fn should_install_crash_handler(_channel: ReleaseChannel) -> bool {
    false
}

pub fn os_name() -> String {
    #[cfg(target_os = "macos")]
    {
        "macOS".to_string()
    }
    #[cfg(target_os = "linux")]
    {
        format!("Linux {}", gpui::guess_compositor())
    }
    #[cfg(target_os = "freebsd")]
    {
        format!("FreeBSD {}", gpui::guess_compositor())
    }

    #[cfg(target_os = "windows")]
    {
        "Windows".to_string()
    }
}

/// Note: This might do blocking IO! Only call from background threads
pub fn os_version() -> String {
    cfg_select! {
       feature = "test-support" => {
           // MacOS branch in particular is quite slow, hence we ought to "avoid" it in tests.
           "test binary".to_owned()
       }
       target_os = "macos" => {
           static MACOS_VERSION_REGEX: LazyLock<Regex> = LazyLock::new(|| {
               Regex::new(r"(\s*\(Build [^)]*[0-9]\))").unwrap()
           });
           use objc2_foundation::NSProcessInfo;
           let process_info = NSProcessInfo::processInfo();
           let version_nsstring = process_info.operatingSystemVersionString();
           // "Version 15.6.1 (Build 24G90)" -> "15.6.1 (Build 24G90)"
           let version_string = version_nsstring.to_string().replace("Version ", "");
           // "15.6.1 (Build 24G90)" -> "15.6.1"
           // "26.0.0 (Build 25A5349a)" -> unchanged (Beta or Rapid Security Response; ends with letter)
           MACOS_VERSION_REGEX
               .replace_all(&version_string, "")
               .to_string()
       }
       any(target_os = "linux", target_os = "freebsd") => {
           use std::path::Path;

           let content = if let Ok(file) = std::fs::read_to_string(&Path::new("/etc/os-release")) {
               file
           } else if let Ok(file) = std::fs::read_to_string(&Path::new("/usr/lib/os-release")) {
               file
           } else if let Ok(file) = std::fs::read_to_string(&Path::new("/var/run/os-release")) {
               file
           } else {
               log::error!(
                   "Failed to load /etc/os-release, /usr/lib/os-release, or /var/run/os-release"
               );
               "".to_string()
           };
           util::parse_os_release(&content).unwrap_or_else(|| "unknown".to_string())
       }
       target_os = "windows" => {
           let mut info = unsafe { std::mem::zeroed() };
           let status = unsafe { windows::Wdk::System::SystemServices::RtlGetVersion(&mut info) };
           if status.is_ok() {
               semver::Version::new(
                   info.dwMajorVersion as _,
                   info.dwMinorVersion as _,
                   info.dwBuildNumber as _,
               )
               .to_string()
           } else {
               "unknown".to_string()
           }
       }
    }
}

impl Telemetry {
    pub fn new(
        _clock: Arc<dyn SystemClock>,
        _client: Arc<HttpClientWithUrl>,
        _cx: &mut App,
    ) -> Arc<Self> {
        Arc::new(Self)
    }

    pub fn log_file_path() -> PathBuf {
        paths::logs_dir().join("telemetry.log")
    }

    pub async fn subscribe_with_history(
        self: &Arc<Self>,
        _fs: Arc<dyn Fs>,
    ) -> TelemetrySubscription {
        let (_sender, receiver) = mpsc::unbounded();
        TelemetrySubscription {
            historical_events: Ok(HistoricalEvents {
                events: Vec::new(),
                parse_error_count: 0,
            }),
            queued_events: Vec::new(),
            live_events: receiver,
        }
    }

    pub fn has_checksum_seed(&self) -> bool {
        false
    }

    pub fn start(
        self: &Arc<Self>,
        _system_id: Option<String>,
        _installation_id: Option<String>,
        _session_id: String,
        _cx: &App,
    ) {
    }
    pub fn metrics_enabled(self: &Arc<Self>) -> bool {
        false
    }
    pub fn diagnostics_enabled(self: &Arc<Self>) -> bool {
        false
    }
    pub fn set_authenticated_user_info(
        self: &Arc<Self>,
        _metrics_id: Option<String>,
        _is_staff: bool,
    ) {
    }
    pub fn report_assistant_event(self: &Arc<Self>, _event: AssistantEventData) {}
    pub fn log_edit_event(self: &Arc<Self>, _environment: &'static str, _is_via_ssh: bool) {}
    pub fn report_discovered_project_type_events(
        self: &Arc<Self>,
        _worktree_id: WorktreeId,
        _updated_entries_set: &UpdatedEntriesSet,
    ) {
    }
    pub fn report_remote_event(
        self: &Arc<Self>,
        _event_json: &str,
        _connection_type: &str,
        _os_name: String,
        _os_version: Option<String>,
        _architecture: String,
    ) -> Result<()> {
        Ok(())
    }

    #[cfg(any(test, feature = "test-support"))]
    pub fn queued_events(self: &Arc<Self>) -> Vec<telemetry_events::FlexibleEvent> {
        Vec::new()
    }

    pub fn metrics_id(self: &Arc<Self>) -> Option<Arc<str>> {
        None
    }
    pub fn system_id(self: &Arc<Self>) -> Option<Arc<str>> {
        None
    }
    pub fn installation_id(self: &Arc<Self>) -> Option<Arc<str>> {
        None
    }
    pub fn is_staff(self: &Arc<Self>) -> Option<bool> {
        None
    }
    pub async fn flush_events_inner(self: &Arc<Self>) -> Result<()> {
        Ok(())
    }
    pub fn flush_events(self: &Arc<Self>) -> Task<()> {
        Task::ready(())
    }
}

pub fn calculate_json_checksum(_json: &impl AsRef<[u8]>) -> Option<String> {
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn legacy_opt_in_settings_cannot_enable_reporting() {
        use settings::Settings as _;
        let mut content = settings::SettingsContent::default();
        let settings = content.telemetry.get_or_insert_default();
        settings.metrics = Some(true);
        settings.diagnostics = Some(true);
        settings.anthropic_retention = Some(true);
        let effective = crate::TelemetrySettings::from_settings(&content);
        assert!(!effective.metrics);
        assert!(!effective.diagnostics);
        assert!(!effective.anthropic_retention);
    }

    #[test]
    fn telemetry_cannot_retain_identifiers_or_remote_events() {
        let telemetry = Arc::new(Telemetry);
        telemetry.set_authenticated_user_info(Some("private-user".into()), true);
        telemetry
            .report_remote_event(
                "not even JSON",
                "ssh",
                "private-host".into(),
                None,
                "private-arch".into(),
            )
            .expect("disabled telemetry must ignore remote payloads");
        assert!(telemetry.metrics_id().is_none());
        assert!(telemetry.system_id().is_none());
        assert!(telemetry.installation_id().is_none());
        assert!(telemetry.queued_events().is_empty());
        assert!(!telemetry.metrics_enabled());
        assert!(!telemetry.diagnostics_enabled());
        assert!(!should_install_crash_handler(ReleaseChannel::Stable));
        assert!(MINIDUMP_ENDPOINT.is_none());
    }
}
