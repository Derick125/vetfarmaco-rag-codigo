import 'dart:async';
import 'dart:convert';

import 'package:app/core/theme/cores.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/consulta/domain/formulario_consulta.dart';
import 'package:app/features/consulta/domain/vocabulario.dart';
import 'package:app/features/consulta/presentation/cubit/consulta_cubit.dart';
import 'package:app/features/consulta/presentation/cubit/consulta_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

/// `/consulta` — formulário estruturado (`docs/FRONTEND_SPEC.md` §9).
///
/// Nesta etapa (4.4): espécie, peso, fármacos e comorbidades. A pergunta e o
/// envio entram na 4.5.
class ConsultaPage extends StatefulWidget {
  /// Cria a tela.
  const new({super.key});

  @override
  State<ConsultaPage> createState() => _ConsultaPageState();
}

class _ConsultaPageState extends State<ConsultaPage> {
  @override
  void initState() {
    super.initState();
    unawaited(context.read<ConsultaCubit>().carregar());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Nova consulta'),
        actions: [
          IconButton(
            tooltip: 'Histórico',
            icon: const Icon(Icons.history),
            onPressed: () => unawaited(context.push('/historico')),
          ),
          IconButton(
            tooltip: 'Ajustes',
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => unawaited(context.push('/ajustes')),
          ),
        ],
      ),
      body: BlocBuilder<ConsultaCubit, ConsultaState>(
        builder: (context, state) => switch (state.status) {
          StatusVocabulario.carregando => const Center(
            child: CircularProgressIndicator(),
          ),
          StatusVocabulario.falha => _Falha(mensagem: state.mensagem),
          StatusVocabulario.pronto => _Formulario(state: state),
        },
      ),
    );
  }
}

class _Falha extends StatelessWidget {
  const new({required this.mensagem});

  final String? mensagem;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              mensagem ?? 'Não foi possível carregar o vocabulário.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            OutlinedButton(
              onPressed: () =>
                  unawaited(context.read<ConsultaCubit>().carregar()),
              child: const Text('Tentar de novo'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Formulario extends StatelessWidget {
  const new({required this.state});

  final ConsultaState state;

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<ConsultaCubit>();
    final tema = Theme.of(context).textTheme;
    final vocabulario = state.vocabulario!;
    final form = state.formulario;
    final rotulo = tema.titleSmall;
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      children: [
        Text('Espécie', style: rotulo),
        const SizedBox(height: 8),
        SegmentedButton<String>(
          emptySelectionAllowed: true,
          showSelectedIcon: false,
          style: const ButtonStyle(
            minimumSize: WidgetStatePropertyAll(Size(0, 48)),
          ),
          segments: [
            for (final e in vocabulario.especies)
              ButtonSegment(value: e, label: Text(_capitalizar(e))),
          ],
          selected: {if (form.especie != null) form.especie!},
          onSelectionChanged: (s) {
            // Tocar na espécie já marcada devolve o conjunto vazio.
            final escolhida = s.isEmpty ? form.especie! : s.first;
            cubit.alterarEspecie(escolhida);
          },
        ),
        const SizedBox(height: 20),
        Text('Peso', style: rotulo),
        const SizedBox(height: 8),
        TextField(
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp('[0-9.,]')),
          ],
          onChanged: cubit.alterarPeso,
          style: const TextStyle(fontFeatures: [FontFeature.tabularFigures()]),
          decoration: InputDecoration(
            hintText: '4,2',
            suffixText: 'kg',
            errorText: form.erroPeso,
            helperText: form.faltaPeso
                ? 'Obrigatório para perguntas sobre dose.'
                : null,
            helperStyle: TextStyle(color: context.cores.iodo),
            border: const OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 20),
        Text('Fármacos em questão', style: rotulo),
        const SizedBox(height: 8),
        if (form.farmacos.isNotEmpty)
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final f in form.farmacos)
                InputChip(
                  label: Text(f),
                  onDeleted: () => cubit.removerFarmaco(f),
                  deleteButtonTooltipMessage: 'Remover $f',
                ),
            ],
          ),
        if (form.farmacos.isNotEmpty) const SizedBox(height: 8),
        _CampoFarmaco(
          vocabulario: vocabulario,
          escolhidos: form.farmacos,
          aoEscolher: cubit.adicionarFarmaco,
        ),
        if (form.semFarmacos)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              'Recomendado: informe ao menos um fármaco.',
              style: tema.bodySmall?.copyWith(color: context.cores.iodo),
            ),
          ),
        const SizedBox(height: 20),
        Text('Condições relevantes', style: rotulo),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final c in vocabulario.comorbidades)
              FilterChip(
                label: Text(c.rotulo),
                selected: form.comorbidades.contains(c.chave),
                onSelected: (_) => cubit.alternarComorbidade(c.chave),
              ),
          ],
        ),
        const SizedBox(height: 20),
        Text('Pergunta', style: rotulo),
        const SizedBox(height: 4),
        Text(
          'Não inclua nomes de tutores, de animais ou números de prontuário.',
          style: tema.bodyMedium?.copyWith(color: context.cores.inkMuted),
        ),
        const SizedBox(height: 8),
        TextField(
          minLines: 3,
          maxLines: 6,
          maxLength: maximoPergunta,
          textCapitalization: TextCapitalization.sentences,
          onChanged: cubit.alterarPergunta,
          decoration: const InputDecoration(
            hintText: 'É seguro repetir meloxicam neste paciente?',
            border: OutlineInputBorder(),
          ),
        ),
        if (state.corpo != null) _Previa(corpo: state.corpo!),
        const SizedBox(height: 16),
        FilledButton(
          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
          onPressed: form.valido && state.corpo != null
              ? () => unawaited(
                  context.push(
                    '/consulta/${DateTime.now().microsecondsSinceEpoch}',
                    extra: state.corpo,
                  ),
                )
              : null,
          child: const Text('Consultar a literatura'),
        ),
      ],
    );
  }
}

/// Expansor com o JSON exato que sairá do aparelho (`FRONTEND_SPEC.md` §9).
class _Previa extends StatelessWidget {
  const new({required this.corpo});

  final CorpoConsulta corpo;

  @override
  Widget build(BuildContext context) {
    final json = const JsonEncoder.withIndent('  ').convert(corpo.paraJson());
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      title: const Text('Ver o que será enviado'),
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          color: context.cores.surface,
          child: SelectableText(
            json,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
          ),
        ),
      ],
    );
  }
}

class _CampoFarmaco extends StatefulWidget {
  const new({
    required this.vocabulario,
    required this.escolhidos,
    required this.aoEscolher,
  });

  final Vocabulario vocabulario;
  final List<String> escolhidos;
  final void Function(String) aoEscolher;

  @override
  State<_CampoFarmaco> createState() => _CampoFarmacoState();
}

class _CampoFarmacoState extends State<_CampoFarmaco> {
  final _controller = TextEditingController();
  final _foco = FocusNode();

  @override
  void dispose() {
    _controller.dispose();
    _foco.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Autocomplete<String>(
      textEditingController: _controller,
      focusNode: _foco,
      optionsBuilder: (valor) => widget.vocabulario.sugerir(
        valor.text,
        excluir: widget.escolhidos.toSet(),
      ),
      onSelected: (nome) {
        widget.aoEscolher(nome);
        // Limpa o campo para encadear outro fármaco.
        _controller.clear();
      },
      fieldViewBuilder: (context, controller, foco, _) => TextField(
        controller: controller,
        focusNode: foco,
        autocorrect: false,
        decoration: const InputDecoration(
          hintText: '+ adicionar fármaco',
          border: OutlineInputBorder(),
        ),
        onTapOutside: (_) => foco.unfocus(),
      ),
      optionsViewBuilder: (context, onSelected, opcoes) => Align(
        alignment: Alignment.topLeft,
        child: Material(
          elevation: 4,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 240, maxWidth: 400),
            child: ListView(
              padding: EdgeInsets.zero,
              shrinkWrap: true,
              children: [
                for (final o in opcoes)
                  ListTile(title: Text(o), onTap: () => onSelected(o)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String _capitalizar(String s) =>
    s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);
