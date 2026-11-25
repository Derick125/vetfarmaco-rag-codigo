import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';

/// Destino para o qual a tela de abertura deve encaminhar o usuário.
enum DestinoInicial {
  /// `/termo` — termo de uso clínico ainda não foi aceito.
  termo,

  /// `/consulta` — app pronto para uso.
  consulta,

  /// Endereço do back-end ausente; a abertura permanece em `FalhaConfig`.
  falhaConfig,
}

/// Decide o destino inicial do app a partir da configuração local.
///
/// Regra (`docs/FRONTEND_SPEC.md` §7): sem endereço de back-end configurado,
/// não há como consultar — `falhaConfig`. Com endereço configurado, o termo
/// de uso clínico ainda não aceito manda para `/termo`; já aceito, para
/// `/consulta`.
class DecidirDestinoInicial {
  /// Cria o caso de uso a partir do repositório de configuração.
  const new(this._repositorio);

  final ConfiguracaoRepository _repositorio;

  /// Decide o destino inicial do app.
  Future<DestinoInicial> call() async {
    final endereco = await _repositorio.enderecoBackend();
    if (endereco == null || endereco.isEmpty) {
      return DestinoInicial.falhaConfig;
    }

    final termoAceitoEm = await _repositorio.termoAceitoEm();
    return termoAceitoEm == null
        ? DestinoInicial.termo
        : DestinoInicial.consulta;
  }
}
