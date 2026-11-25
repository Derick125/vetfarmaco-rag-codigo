import 'package:app/core/config/app_config.dart';
import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:injectable/injectable.dart';

/// Nome da caixa `hive_ce` que guarda a configuração local do app.
const nomeCaixaConfiguracao = 'configuracao';

/// Chave do endereço do back-end definido em `/ajustes` (sobrepõe o
/// `--dart-define`).
const chaveEnderecoBackend = 'enderecoBackend';

/// Chave da data/hora do aceite do termo de uso.
const chaveTermoAceitoEm = 'termoAceitoEm';

/// Implementação de [ConfiguracaoRepository] sobre uma caixa `hive_ce`.
@LazySingleton(as: ConfiguracaoRepository)
class ConfiguracaoRepositoryImpl implements ConfiguracaoRepository {
  /// Cria o repositório a partir da caixa `hive_ce` de configuração e da
  /// configuração de build.
  const new(this._caixa, this._config);

  final Box<dynamic> _caixa;
  final AppConfig _config;

  /// Endereço salvo em `/ajustes`, se houver; senão o do `--dart-define`.
  @override
  Future<String?> enderecoBackend() async {
    final salvo = (_caixa.get(chaveEnderecoBackend) as String?)?.trim();
    if (salvo != null && salvo.isNotEmpty) return salvo;
    final padrao = _config.apiBaseUrl.trim();
    return padrao.isEmpty ? null : padrao;
  }

  @override
  Future<DateTime?> termoAceitoEm() async =>
      _caixa.get(chaveTermoAceitoEm) as DateTime?;
}
