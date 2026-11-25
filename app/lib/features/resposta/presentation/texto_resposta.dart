import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_state.dart';
import 'package:app/features/resposta/presentation/widgets/ancora_citacao.dart';

/// Citações que sustentam [paragrafo], em ordem de índice.
///
/// Vazio enquanto o evento `citacoes` não chegou: sem ele não há número a
/// mostrar nem trecho a abrir.
List<Citacao> citacoesDoParagrafo(
  EventoParagrafo paragrafo,
  List<Citacao> citacoes,
) => citacoesPorChunk(paragrafo.chunkIds, citacoes);

/// Citações cujos `chunk_id` estão em [chunkIds], em ordem de índice.
List<Citacao> citacoesPorChunk(List<String> chunkIds, List<Citacao> citacoes) =>
    citacoes.where((c) => chunkIds.contains(c.chunkId)).toList()
      ..sort((a, b) => a.indice.compareTo(b.indice));

/// Título da tela: `Meloxicam · felino · 4,2 kg`.
String resumoConsulta(CorpoConsulta c) {
  final farmacos = c.farmacos.map(_capitalizar).join(', ');
  final partes = [
    if (farmacos.isNotEmpty) farmacos,
    ?c.especie,
    if (c.pesoKg != null) pesoEmKg(c.pesoKg!),
  ];
  return partes.isEmpty ? 'Resposta' : partes.join(' · ');
}

/// Peso legível: `4,2 kg`.
String pesoEmKg(double kg) => '${_numero(kg)} kg';

/// Detalhes técnicos de [fim] além da linha do rodapé (nível de raciocínio,
/// tokens e custo); vazio quando o servidor não os enviou.
List<String> detalhesRodape(EventoFim fim) {
  final tokens = [
    if (fim.inputTokens != null) '${fim.inputTokens} entrada',
    if (fim.outputTokens != null) '${fim.outputTokens} saída',
    if (fim.thoughtTokens != null) '${fim.thoughtTokens} raciocínio',
  ];
  return [
    if (fim.thinkingLevel != null) 'Raciocínio: ${fim.thinkingLevel}',
    if (tokens.isNotEmpty) 'Tokens: ${tokens.join(' · ')}',
    if (fim.custoUsd != null)
      'Custo estimado: US\$ ${_decimal(fim.custoUsd!, 4)}',
  ];
}

/// Rodapé: confiança, modelo, data e tempos do servidor (TCC §4.7).
String rodapeResposta({
  required EventoFim fim,
  DateTime? geradaEm,
  bool incompleta = false,
}) {
  final nivel = fim.nivelConfianca == NivelConfianca.semEvidencia
      ? 'sem evidência'
      : fim.nivelConfianca.name;
  final t = fim.tempos;
  return [
    'Confiança $nivel',
    fim.modelo,
    ?(geradaEm == null ? null : _data(geradaEm)),
    if (t.primeiroParagrafoValidado != null)
      '${_segundos(t.primeiroParagrafoValidado!)} até o primeiro parágrafo',
    if (t.total != null) '${_segundos(t.total!)} total',
    if (incompleta) 'resposta incompleta',
  ].join(' · ');
}

/// Texto para a área de transferência: parágrafos com `[n]` e a lista de
/// evidências — o texto copiado inclui as citações (`FRONTEND_SPEC.md` §10).
String textoParaCopiar(RespostaState s) {
  final b = StringBuffer();
  final alerta = s.alerta;
  if (alerta != null) {
    final palavra = alerta.severidade == SeveridadeAlerta.contraindicacao
        ? 'CONTRAINDICAÇÃO'
        : 'CAUTELA';
    b.writeln('$palavra: ${alerta.texto}\n');
  }
  for (final p in s.paragrafos) {
    final marcas = citacoesDoParagrafo(
      p,
      s.citacoes,
    ).map((c) => '[${c.indice}]').join();
    b.writeln('${p.texto}${marcas.isEmpty ? '' : ' $marcas'}\n');
  }
  if (s.citacoes.isNotEmpty) {
    b.writeln('Evidência:');
    for (final c in s.citacoes) {
      b.writeln('[${c.indice}] "${c.trecho}" — ${descricaoCitacao(c)}');
    }
  }
  final fim = s.fim;
  if (fim != null) {
    b
      ..writeln()
      ..writeln(rodapeResposta(fim: fim, geradaEm: s.geradaEm));
  }
  return b.toString().trimRight();
}

String _capitalizar(String s) =>
    s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

String _numero(double n) => n
    .toStringAsFixed(2)
    .replaceFirst(RegExp(r'\.?0+$'), '')
    .replaceAll('.', ',');

String _decimal(double n, int casas) =>
    n.toStringAsFixed(casas).replaceAll('.', ',');

String _segundos(double ms) =>
    '${(ms / 1000).toStringAsFixed(1).replaceAll('.', ',')} s';

/// `dd/MM` — formato do selo de cache.
String diaMes(DateTime d) =>
    '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}';

String _data(DateTime d) {
  String dois(int n) => n.toString().padLeft(2, '0');
  return '${dois(d.day)}/${dois(d.month)}/${d.year} ${dois(d.hour)}:${dois(d.minute)}';
}
