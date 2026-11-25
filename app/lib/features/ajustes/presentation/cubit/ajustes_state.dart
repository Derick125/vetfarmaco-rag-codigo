import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:equatable/equatable.dart';

/// Situação do teste de conexão com o back-end.
enum StatusTeste {
  /// Nenhum teste feito.
  ocioso,

  /// Chamando `/health`.
  testando,

  /// O back-end respondeu.
  ok,

  /// O teste falhou; veja `AjustesState.mensagem`.
  falha,
}

/// Estado da tela de ajustes (só o endereço do back-end).
class AjustesState extends Equatable {
  /// Cria o estado.
  const new({
    this.endereco = '',
    this.status = StatusTeste.ocioso,
    this.mensagem,
    this.salvo = false,
    this.condicao = CondicaoCampanha.naoInformada,
  });

  /// Endereço em vigor ao abrir a tela.
  final String endereco;

  /// Situação do teste de conexão.
  final StatusTeste status;

  /// Mensagem de falha (teste ou validação), se houver.
  final String? mensagem;

  /// `true` depois de gravar o endereço com sucesso.
  final bool salvo;

  /// Condição de rede da campanha (gravada em cada registro de telemetria).
  final CondicaoCampanha condicao;

  /// Cópia com campos trocados; [mensagem] é sempre substituída.
  AjustesState copiar({
    String? endereco,
    StatusTeste? status,
    String? mensagem,
    bool? salvo,
    CondicaoCampanha? condicao,
  }) => AjustesState(
    endereco: endereco ?? this.endereco,
    status: status ?? this.status,
    mensagem: mensagem,
    salvo: salvo ?? this.salvo,
    condicao: condicao ?? this.condicao,
  );

  @override
  List<Object?> get props => [endereco, status, mensagem, salvo, condicao];
}
