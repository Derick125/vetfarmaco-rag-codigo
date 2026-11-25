import 'package:equatable/equatable.dart';

/// Nível de confiança declarado pelo back-end no evento `fim`.
enum NivelConfianca {
  /// Alta.
  alta,

  /// Média.
  media,

  /// Baixa.
  baixa,

  /// O acervo não sustenta a resposta: resultado legítimo, não erro.
  semEvidencia,
}

/// Severidade do alerta de segurança.
enum SeveridadeAlerta {
  /// Contraindicação.
  contraindicacao,

  /// Cautela.
  cautela,
}

/// Trecho do acervo que sustenta uma afirmação.
class Citacao extends Equatable {
  /// Cria a citação.
  const new({
    required this.chunkId,
    required this.indice,
    required this.trecho,
    required this.fonte,
    this.capitulo,
    this.pagina,
  });

  /// Identificador do chunk citado.
  final String chunkId;

  /// Número exibido na âncora.
  final int indice;

  /// Trecho literal do acervo.
  final String trecho;

  /// Fonte, ex.: `Spinosa et al. (2017)`.
  final String fonte;

  /// Capítulo, se houver.
  final String? capitulo;

  /// Página, se houver.
  final int? pagina;

  @override
  List<Object?> get props => [chunkId, indice, trecho, fonte, capitulo, pagina];
}

/// Tempos do servidor (`fim.tempos`), em milissegundos.
class TemposServidor extends Equatable {
  /// Cria os tempos.
  const new({this.primeiroToken, this.primeiroParagrafoValidado, this.total});

  /// Primeiro token do modelo.
  final double? primeiroToken;

  /// Primeiro parágrafo validado.
  final double? primeiroParagrafoValidado;

  /// Total.
  final double? total;

  @override
  List<Object?> get props => [primeiroToken, primeiroParagrafoValidado, total];
}

/// Eventos do stream de `POST /consulta` (`docs/RAG_SPEC.md` §7.1).
///
/// O cliente nunca recebe token bruto: cada evento é um objeto já validado.
sealed class EventoResposta extends Equatable {
  const new();
}

/// Fim da busca híbrida; primeiro evento do stream.
final class EventoRecuperacao extends EventoResposta {
  /// Cria o evento.
  const new({required this.chunks, required this.ms, this.thinkingLevel});

  /// Trechos recuperados.
  final int chunks;

  /// Duração da recuperação no servidor.
  final double ms;

  /// Nível de raciocínio decidido pelo servidor (`low` ou `high`); `null` em
  /// servidor que ainda não o informa.
  final String? thinkingLevel;

  @override
  List<Object?> get props => [chunks, ms, thinkingLevel];
}

/// Parágrafo já validado.
final class EventoParagrafo extends EventoResposta {
  /// Cria o evento.
  const new({
    required this.indice,
    required this.texto,
    required this.chunkIds,
  });

  /// Posição entre os parágrafos emitidos.
  final int indice;

  /// Texto do parágrafo.
  final String texto;

  /// Chunks que o sustentam; vazio = sem lastro documental.
  final List<String> chunkIds;

  @override
  List<Object?> get props => [indice, texto, chunkIds];
}

/// Trechos citados, depois da validação completa.
final class EventoCitacoes extends EventoResposta {
  /// Cria o evento.
  const new(this.citacoes);

  /// Citações validadas.
  final List<Citacao> citacoes;

  @override
  List<Object?> get props => [citacoes];
}

/// Alerta de segurança, só depois da validação completa.
final class EventoAlerta extends EventoResposta {
  /// Cria o evento.
  const new({
    required this.severidade,
    required this.texto,
    required this.chunkIds,
  });

  /// Severidade.
  final SeveridadeAlerta severidade;

  /// Texto do alerta.
  final String texto;

  /// Chunks que o sustentam.
  final List<String> chunkIds;

  @override
  List<Object?> get props => [severidade, texto, chunkIds];
}

/// Último evento de sucesso.
final class EventoFim extends EventoResposta {
  /// Cria o evento.
  const new({
    required this.nivelConfianca,
    required this.modelo,
    required this.tempos,
    this.thinkingLevel,
    this.inputTokens,
    this.outputTokens,
    this.thoughtTokens,
    this.custoUsd,
  });

  /// Nível de confiança.
  final NivelConfianca nivelConfianca;

  /// Versão do modelo (TCC §4.7).
  final String modelo;

  /// Tempos do servidor.
  final TemposServidor tempos;

  /// Nível de raciocínio da geração (`low` ou `high`).
  final String? thinkingLevel;

  /// Tokens de entrada.
  final int? inputTokens;

  /// Tokens de saída.
  final int? outputTokens;

  /// Tokens de raciocínio.
  final int? thoughtTokens;

  /// Custo da consulta em dólares.
  final double? custoUsd;

  @override
  List<Object?> get props => [
    nivelConfianca,
    modelo,
    tempos,
    thinkingLevel,
    inputTokens,
    outputTokens,
    thoughtTokens,
    custoUsd,
  ];
}
