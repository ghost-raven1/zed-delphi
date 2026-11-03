use anyhow::{Result, bail};
use async_trait::async_trait;
use collections::HashMap;
use gpui::AsyncApp;
use language::{LanguageName, LspAdapter, LspAdapterDelegate, LspInstaller, Toolchain};
use lsp::{LanguageServerBinary, LanguageServerName, Uri};
use project::lsp_store::language_server_settings;
use serde_json::{Value, json};
use std::{future::Future, path::PathBuf, sync::Arc};
use util::merge_json_value_into;

/// The two compilers have different project models; the user selects their server explicitly.
pub enum DelphiLspAdapter {
    FreePascal,
    Embarcadero,
}

impl DelphiLspAdapter {
    fn executable(&self) -> &'static str {
        match self {
            Self::FreePascal => "pasls",
            Self::Embarcadero => "DelphiLSP",
        }
    }

    fn initialization_options_with_overrides(&self, overrides: Option<Value>) -> Value {
        let mut options = match self {
            Self::FreePascal => json!({
                "checkSyntax": true,
                "publishDiagnostics": true,
                "fpcOptions": ["-Mdelphi"]
            }),
            Self::Embarcadero => json!({
                "serverType": "controller",
                "agentCount": 2,
                "returnDccFlags": false,
                "returnHoverModel": false,
                "storeProjectSettings": false
            }),
        };
        if let Some(overrides) = overrides {
            merge_json_value_into(overrides, &mut options);
        }
        options
    }
}

impl LspInstaller for DelphiLspAdapter {
    type BinaryVersion = ();

    async fn check_if_user_installed(
        &self,
        delegate: &Arc<dyn LspAdapterDelegate>,
        _: Option<Toolchain>,
        _: &AsyncApp,
    ) -> Option<LanguageServerBinary> {
        Some(LanguageServerBinary {
            path: delegate.which(self.executable().as_ref()).await?,
            arguments: Vec::new(),
            env: Some(delegate.shell_env().await),
        })
    }

    async fn fetch_latest_server_version(
        &self,
        _: &Arc<dyn LspAdapterDelegate>,
        _: bool,
        _: &mut AsyncApp,
    ) -> Result<()> {
        bail!(
            "Установите {} локально и задайте lsp.{}.binary.path; автоматическая загрузка не поддерживается",
            self.executable(),
            self.name().0.as_str()
        )
    }

    fn fetch_server_binary(
        &self,
        _: (),
        _: PathBuf,
        _: &Arc<dyn LspAdapterDelegate>,
    ) -> impl Send + Future<Output = Result<LanguageServerBinary>> + use<> {
        async {
            bail!("Языковые серверы Delphi необходимо установить локально")
        }
    }

    async fn cached_server_binary(
        &self,
        _: PathBuf,
        _: &dyn LspAdapterDelegate,
    ) -> Option<LanguageServerBinary> {
        None
    }
}

#[async_trait(?Send)]
impl LspAdapter for DelphiLspAdapter {
    fn name(&self) -> LanguageServerName {
        LanguageServerName::new_static(match self {
            Self::FreePascal => "pasls",
            Self::Embarcadero => "delphilsp",
        })
    }

    fn is_opt_in_for(&self, _: &LanguageName) -> bool {
        true
    }

    fn language_ids(&self) -> HashMap<LanguageName, String> {
        HashMap::from_iter([("Delphi".into(), "pascal".into())])
    }

    async fn initialization_options(
        self: Arc<Self>,
        delegate: &Arc<dyn LspAdapterDelegate>,
        cx: &mut AsyncApp,
    ) -> Result<Option<Value>> {
        let overrides = cx.update(|cx| {
            language_server_settings(delegate.as_ref(), &self.name(), cx)
                .and_then(|settings| settings.initialization_options.clone())
        });
        Ok(Some(self.initialization_options_with_overrides(overrides)))
    }

    async fn workspace_configuration(
        self: Arc<Self>,
        delegate: &Arc<dyn LspAdapterDelegate>,
        _: Option<Toolchain>,
        _: Option<Uri>,
        cx: &mut AsyncApp,
    ) -> Result<Value> {
        Ok(cx
            .update(|cx| {
                language_server_settings(delegate.as_ref(), &self.name(), cx)
                    .and_then(|settings| settings.settings.clone())
            })
            .unwrap_or_else(|| json!({})))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn delphi_lsp_uses_standard_hover_and_enables_diagnostics() {
        let options = DelphiLspAdapter::Embarcadero.initialization_options_with_overrides(None);
        assert_eq!(options["serverType"], "controller");
        assert_eq!(options["agentCount"], 2);
        assert_eq!(options["returnHoverModel"], false);
        assert_eq!(options["storeProjectSettings"], false);
    }

    #[test]
    fn pasls_enables_diagnostics_but_respects_explicit_project_overrides() {
        let options = DelphiLspAdapter::FreePascal.initialization_options_with_overrides(None);
        assert_eq!(options["checkSyntax"], true);
        assert_eq!(options["publishDiagnostics"], true);
        assert_eq!(options["fpcOptions"], json!(["-Mdelphi"]));
        let options =
            DelphiLspAdapter::FreePascal.initialization_options_with_overrides(Some(json!({
                "checkSyntax": false,
                "fpcOptions": ["-Mobjfpc"]
            })));
        assert_eq!(options["checkSyntax"], false);
        assert_eq!(options["publishDiagnostics"], true);
        assert_eq!(options["fpcOptions"], json!(["-Mobjfpc"]));
    }

    #[test]
    fn servers_require_an_explicit_toolchain_choice() {
        for adapter in [DelphiLspAdapter::FreePascal, DelphiLspAdapter::Embarcadero] {
            assert!(adapter.is_opt_in_for(&"Delphi".into()));
            assert_eq!(
                adapter
                    .language_ids()
                    .get(&LanguageName::from("Delphi"))
                    .unwrap(),
                "pascal"
            );
        }
    }
}
