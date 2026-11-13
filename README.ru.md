# modstride

modstride помогает переносить существующие моды Minecraft между версиями игры, загрузчиками и пространствами имён маппингов. Утилита анализирует исходный проект или JAR, строит план, создаёт отдельную рабочую копию и сохраняет результаты проверок. Её можно запускать без ИИ. Для Codex, Claude Code и других агентов доступен переносимый Agent Skill. [Подключение агентов](docs/agents.md)

## Установка и пример

В корне репозитория используйте Python 3.11 или новее. Пути с пробелами заключайте в кавычки.

```sh
python -m pip install .
modstride scan examples/sample-source-mod
modstride plan examples/sample-source-mod --to-version 1.20.4 --to-loader fabric --output-dir work/plan
modstride apply --plan work/plan/migration-plan.json --workspace work/target --dry-run
modstride apply --plan work/plan/migration-plan.json --workspace work/target
modstride verify --workspace work/target
modstride report --workspace work/target
```

Демонстрационный мод Copper Token переносится с Fabric 1.20.1 на 1.20.4. Два правила обновляют точные версии в настройках Gradle и метаданных Fabric. Обе версии мода собраны на Windows с JDK 17 и Gradle 8.7. Для сборки проверенного проекта добавьте `--run-gradle` к команде `verify`. Запуск игры и сохранение игрового поведения требуют отдельных проверок. [Пошаговый пример и сценарии проверки](examples/sample-migration/README.md)

`resume --workspace work/target` показывает завершённые операции и оставшиеся задачи. Отчёты находятся в `work/target/.modstride`.

Для Forge, NeoForge и Quilt доступны анализ и планирование. Перенос Java API, сложных сетевых и графических функций выполняется вручную или агентом. Для Horizon доступна экспериментальная оценка возможности переписать мод. [Матрица поддержки](docs/supported-targets.md)

Оригинальный код и пример распространяются по лицензии [MIT](LICENSE). Для сторонних модов и игровых файлов действуют их собственные лицензии. [Как внести вклад](CONTRIBUTING.md)
