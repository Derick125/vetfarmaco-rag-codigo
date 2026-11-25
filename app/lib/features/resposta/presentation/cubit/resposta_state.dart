import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:equatable/equatable.dart';

/// Fase da resposta em `/consulta/:id` (`docs/FRONTEND_SPEC.md` §10).
enum FaseResposta {
  /// Buscando na literatura.
  recuperando,

  /// Recebendo parágrafos já validados.
  transmitindo,

  /// `fim` recebido com evidência.
  concluida,

  /// `fim` com `semEvidencia`: sucesso, não erro.
  semEvidencia,

  /// Falha; veja `RespostaState.mensagem`.
  falha,

  /// Sem rede e sem resposta guardada para esta consulta.
  offlineSemCache,
}

/// Parágrafo recebido, já validado pelo back-end.
typedef ParagrafoRecebido = EventoParagrafo;

/// Estado da resposta, acumulado a partir dos eventos SSE.
class RespostaState extends Equatable {
  /// Cria o estado.
  const new({
    this.fase = FaseResposta.recuperando,
    this.chunks,
    this.paragrafos = const [],
    this.citacoes = const [],
    this.alerta,
    this.fim,
    this.mensagem,
    this.incompleta = false,
    this.geradaEm,
    this.origemCache = false,
    this.salva = false,
  });

  /// Fase atual.
  final FaseResposta fase;

  /// Trechos recuperados, depois do evento `recuperacao`.
  final int? chunks;

  /// Parágrafos validados, na ordem de chegada.
  final List<ParagrafoRecebido> paragrafos;

  /// Citações, depois da validação completa.
  final List<Citacao> citacoes;

  /// Alerta de segurança, se o servidor enviou.
  final EventoAlerta? alerta;

  /// Evento `fim`, quando recebido.
  final EventoFim? fim;

  /// Mensagem da falha.
  final String? mensagem;

  /// A conexão caiu no meio: os parágrafos são parciais.
  final bool incompleta;

  /// Quando o `fim` chegou (data exibida no rodapé, TCC §4.7).
  final DateTime? geradaEm;

  /// Resposta lida do cache: exibe o selo de data, nunca se disfarça de nova.
  final bool origemCache;

  /// Já está no histórico.
  final bool salva;

  /// Cópia com campos trocados; [mensagem] é sempre substituída.
  RespostaState copiar({
    FaseResposta? fase,
    int? chunks,
    List<ParagrafoRecebido>? paragrafos,
    List<Citacao>? citacoes,
    EventoAlerta? alerta,
    EventoFim? fim,
    String? mensagem,
    bool? incompleta,
    DateTime? geradaEm,
    bool? origemCache,
    bool? salva,
  }) => RespostaState(
    fase: fase ?? this.fase,
    chunks: chunks ?? this.chunks,
    paragrafos: paragrafos ?? this.paragrafos,
    citacoes: citacoes ?? this.citacoes,
    alerta: alerta ?? this.alerta,
    fim: fim ?? this.fim,
    mensagem: mensagem,
    incompleta: incompleta ?? this.incompleta,
    geradaEm: geradaEm ?? this.geradaEm,
    origemCache: origemCache ?? this.origemCache,
    salva: salva ?? this.salva,
  );

  @override
  List<Object?> get props => [
    fase,
    chunks,
    paragrafos,
    citacoes,
    alerta,
    fim,
    mensagem,
    incompleta,
    geradaEm,
    origemCache,
    salva,
  ];
}
