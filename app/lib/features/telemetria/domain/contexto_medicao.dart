import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:equatable/equatable.dart';

/// O que se sabe no momento do envio e acompanha o registro de telemetria.
class ContextoMedicao extends Equatable {
  /// Cria o contexto.
  const new({
    required this.rede,
    this.condicao = CondicaoCampanha.naoInformada,
    this.modelo,
  });

  /// Conexão do aparelho (`wifi`, `mobile`, `none`…).
  final String rede;

  /// Condição da campanha escolhida em Ajustes.
  final CondicaoCampanha condicao;

  /// Versão do modelo informada por `GET /health` no envio; `null` se o
  /// back-end não respondeu.
  final String? modelo;

  @override
  List<Object?> get props => [rede, condicao, modelo];
}
