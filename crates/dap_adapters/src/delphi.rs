use std::{ffi::OsStr, path::PathBuf, sync::Arc};

use anyhow::{Context as _, Result, ensure};
use async_trait::async_trait;
use collections::HashMap;
use dap::{
    StartDebuggingRequestArguments,
    adapters::{
        DapDelegate, DebugAdapter, DebugAdapterBinary, DebugAdapterName, DebugTaskDefinition,
    },
};
use gpui::AsyncApp;
use serde_json::json;
use task::{DebugRequest, DebugScenario, ZedDebugConfig};

/// Uses the separately installed MCA Delphi debugger over stdio without downloading binaries.
pub(crate) struct DelphiDebugAdapter;

#[async_trait(?Send)]
impl DebugAdapter for DelphiDebugAdapter {
    fn name(&self) -> DebugAdapterName {
        "Delphi".into()
    }

    fn adapter_language_name(&self) -> Option<language::LanguageName> {
        Some("Delphi".into())
    }

    async fn config_from_zed_format(&self, scenario: ZedDebugConfig) -> Result<DebugScenario> {
        let config = match scenario.request {
            DebugRequest::Launch(launch) => {
                ensure!(
                    launch.env.is_empty(),
                    "Set Delphi debug environment in dap.Delphi.env; the adapter does not expose a launch env field"
                );
                ensure!(
                    launch.cwd.is_none(),
                    "Use a .zed/debug.json Delphi profile; the adapter does not expose a launch cwd field"
                );
                json!({
                    "request": "launch",
                    "program": launch.program,
                    "args": launch.args,
                    "stopAtEntry": scenario.stop_on_entry.unwrap_or(false),
                })
            }
            DebugRequest::Attach(attach) => json!({
                "request": "attach",
                "processId": attach.process_id,
            }),
        };
        Ok(DebugScenario {
            adapter: scenario.adapter,
            label: scenario.label,
            build: None,
            tcp_connection: None,
            config,
        })
    }

    fn dap_schema(&self) -> serde_json::Value {
        json!({
            "type": "object",
            "required": ["request"],
            "properties": {
                "request": {"enum": ["launch", "attach"]},
                "program": {"type": "string"},
                "processId": {"type": "integer", "minimum": 1},
                "processName": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
                "sourceRoot": {"type": "string"},
                "sourceSearchPaths": {"type": "array", "items": {"type": "string"}},
                "mapFile": {"type": "string"},
                "rsmFile": {"type": "string"},
                "stopAtEntry": {"type": "boolean"},
                "killOnDetach": {"type": "boolean"}
            },
            "allOf": [{
                "if": {"properties": {"request": {"const": "launch"}}},
                "then": {"required": ["program"]},
                "else": {"anyOf": [{"required": ["processId"]}, {"required": ["processName"]}]}
            }]
        })
    }

    async fn get_binary(
        &self,
        delegate: &Arc<dyn DapDelegate>,
        config: &DebugTaskDefinition,
        user_installed_path: Option<PathBuf>,
        user_args: Option<Vec<String>>,
        user_env: Option<HashMap<String, String>>,
        _: &mut AsyncApp,
    ) -> Result<DebugAdapterBinary> {
        let path = match user_installed_path {
            Some(path) => path,
            None => delegate
                .which(OsStr::new("VisualStudioCodeDelphiDebugger.exe"))
                .await
                .context("Install the Windows MCA Delphi debug adapter and set dap.Delphi.binary. On macOS/Linux use an explicitly configured Windows transport with source-path mapping.")?,
        };
        let command = path
            .to_str()
            .context("Delphi debug adapter path is not valid Unicode")?;
        ensure!(!command.is_empty(), "Delphi debug adapter path is empty");
        let mut envs = delegate.shell_env().await;
        envs.extend(user_env.unwrap_or_default());
        Ok(DebugAdapterBinary {
            command: Some(command.into()),
            arguments: user_args.unwrap_or_default(),
            envs,
            cwd: Some(delegate.worktree_root_path().into()),
            connection: None,
            request_args: StartDebuggingRequestArguments {
                request: self.request_kind(&config.config).await?,
                configuration: config.config.clone(),
            },
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[gpui::test]
    async fn configured_transport_preserves_arguments_and_target_paths(
        cx: &mut gpui::TestAppContext,
    ) {
        let config = DebugTaskDefinition {
            label: "Delphi remote".into(),
            adapter: "Delphi".into(),
            config: json!({"request": "launch", "program": "C:\\My App\\app.exe", "stopAtEntry": true}),
            tcp_connection: None,
        };
        let args = vec!["-T".into(), "builder".into(), "command with spaces".into()];
        let binary = DelphiDebugAdapter
            .get_binary(
                &crate::test_mocks::MockDelegate::new(),
                &config,
                Some(PathBuf::from("/usr/bin/ssh")),
                Some(args.clone()),
                Some(HashMap::from_iter([("TEST_ENV".into(), "value".into())])),
                &mut cx.to_async(),
            )
            .await
            .unwrap();
        assert_eq!(binary.arguments, args);
        assert_eq!(binary.request_args.configuration, config.config);
        assert_eq!(
            binary.envs.get("TEST_ENV").map(String::as_str),
            Some("value")
        );
        assert!(binary.connection.is_none());
    }
}
