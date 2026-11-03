> [!IMPORTANT]
> Remove this line to confirm you've reviewed this PR before submitting.

## Форк Zed Delphi

Встроенная поддержка Object Pascal. Телеметрия настольного приложения удалена.
См. [настройку и результаты проверок](FORK.md), [работу с Delphi](docs/src/languages/delphi.md)
и [релиз 1.0.1](https://github.com/ghost-raven1/zed-delphi/releases/tag/v1.0.1).
Опубликованы пакеты с русским интерфейсом для macOS ARM64 и Ubuntu 24.04
x86_64/ARM64. Доступны [единый установщик и диагностика окружения](script/delphi/INSTALL-RU.md).
Готовый Windows-пакет и полная совместимость редактора с Astra пока не подтверждены.
Визуального дизайнера VCL/FMX нет; [полная поддержка Delphi 10.3](script/delphi/DELPHI-10.3-RU.md)
остаётся отдельной незавершённой задачей.

# Zed

[![Zed](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/zed-industries/zed/main/assets/badge/v0.json)](https://zed.dev)
[![CI](https://github.com/zed-industries/zed/actions/workflows/run_tests.yml/badge.svg)](https://github.com/zed-industries/zed/actions/workflows/run_tests.yml)

Добро пожаловать в Zed — высокопроизводительный редактор кода с совместной работой от создателей [Atom](https://github.com/atom/atom) и [Tree-sitter](https://github.com/tree-sitter/tree-sitter).

---

### Установка

Пакеты этого форка доступны в [GitHub Releases](https://github.com/ghost-raven1/zed-delphi/releases).
Используйте [руководство установки Zed Delphi](script/delphi/INSTALL-RU.md).
Обычный пакет Zed с сайта upstream не содержит изменений этого форка.

Другие платформы пока не поддерживаются:

- Веб-версия ([обсуждение разработки](https://github.com/zed-industries/zed/discussions/26195))

### Разработка Zed

- [Сборка Zed для macOS](./docs/src/development/macos.md)
- [Сборка Zed для Linux](./docs/src/development/linux.md)
- [Сборка Zed для Windows](./docs/src/development/windows.md)

### Участие в разработке

О том, как помочь развитию Zed, читайте в [CONTRIBUTING.md](./CONTRIBUTING.md).

Команда Zed Industries также ищет сотрудников: открытые позиции опубликованы на [странице вакансий](https://zed.dev/jobs).

### Лицензирование

Исходный код Zed распространяется преимущественно под лицензией GPL-3.0-or-later; для отмеченных компонентов действует Apache-2.0.

Для успешного прохождения CI необходимо корректно указать лицензии сторонних зависимостей.

Для автоматизации соблюдения лицензий открытого ПО используется [`cargo-about`](https://github.com/EmbarkStudios/cargo-about). Если CI завершается с ошибкой, проверьте следующее:

- Если для созданного вами крейта появляется ошибка `no license specified`, добавьте `publish = false` в раздел `[package]` его Cargo.toml.
- Если для зависимости появляется ошибка `failed to satisfy license requirements`, сначала выясните, под какой лицензией распространяется проект и достаточно ли этой системы для соблюдения её требований. При сомнениях обратитесь к юристу. Убедившись, что система подходит, добавьте SPDX-идентификатор лицензии в массив `accepted` файла `script/licenses/zed-licenses.toml`.
- Если `cargo-about` не находит лицензию зависимости, добавьте уточнение в конец `script/licenses/zed-licenses.toml`, как описано в [руководстве cargo-about](https://embarkstudios.github.io/cargo-about/cli/generate/config.html#crate-configuration).

## Финансовая поддержка

Zed разрабатывает коммерческая компания **Zed Industries, Inc.**.

Поддержать проект финансово можно через GitHub Sponsors.
Средства поступают напрямую в Zed Industries и учитываются как обычный доход компании.
Финансовая поддержка не предоставляет дополнительных привилегий или прав.
