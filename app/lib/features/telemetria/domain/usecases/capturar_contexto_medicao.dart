import 'package:app/features/ajustes/domain/endereco_backend.dart';
import 'package:app/features/ajustes/domain/repositories/ajustes_repository.dart';
import 'package:app/features/ajustes/domain/usecases/obter_endereco_backend.dart';
import 'package:app/features/telemetria/domain/contexto_medicao.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';

/// Reúne, no envio da consulta, rede, condição da campanha e modelo.
///
/// O modelo vem de `GET /health`: assim a medição o carrega mesmo que a
/// consulta falhe antes do evento `fim` (TCC §4.7). Sem rede, vale o último
/// modelo que o `/health` informou. Nunca lança.
class CapturarContextoMedicao {
  /// Cria o caso de uso.
  const new(this._rede, this._ajustes, this._endereco);

  final CondicaoRede _rede;
  final AjustesRepository _ajustes;
  final ObterEnderecoBackend _endereco;

  /// Contexto de medição do momento do envio.
  Future<ContextoMedicao> call() async {
    final (rede, condicao, modelo) = await (
      _rede.atual(),
      _ajustes.condicaoCampanha(),
      _modelo(),
    ).wait;
    return ContextoMedicao(rede: rede, condicao: condicao, modelo: modelo);
  }

  Future<String?> _modelo() async =>
      await _modeloDaSaude() ?? await _ajustes.ultimoModeloConhecido();

  Future<String?> _modeloDaSaude() async {
    final bruto = await _endereco();
    if (bruto == null) return null;
    final endereco = normalizarEndereco(bruto).toNullable();
    if (endereco == null) return null;
    return (await _ajustes.consultarSaude(endereco)).toNullable()?.modeloId;
  }
}
