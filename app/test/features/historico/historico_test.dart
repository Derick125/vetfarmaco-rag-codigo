import 'dart:async';
import 'dart:io';

import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/historico/data/repositories/resposta_cache_repository_impl.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:app/features/historico/domain/usecases/listar_historico.dart';
import 'package:app/features/historico/domain/usecases/remover_resposta_salva.dart';
import 'package:app/features/historico/presentation/cubit/historico_cubit.dart';
import 'package:app/features/historico/presentation/cubit/historico_state.dart';
import 'package:app/features/historico/presentation/pages/historico_page.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/domain/usecases/realizar_consulta.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_cubit.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_state.dart';
import 'package:app/features/resposta/presentation/pages/resposta_page.dart';
import 'package:app/features/telemetria/domain/registro_telemetria.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:mocktail/mocktail.dart';

import '../../helpers/telemetria_fakes.dart';

class _MockRealizar extends Mock implements RealizarConsulta;

const _corpo = CorpoConsulta(
  pergunta: 'É seguro repetir meloxicam?',
  complexidadeDica: 'baixa',
  especie: 'felino',
  pesoKg: 4.2,
  farmacos: ['meloxicam'],
);

const _outro = CorpoConsulta(pergunta: 'Outra?', complexidadeDica: 'alta');

const _p0 = EventoParagrafo(
  indice: 1,
  texto: 'Meloxicam é um AINE.',
  chunkIds: ['c1'],
);
const _c1 = Citacao(
  chunkId: 'c1',
  indice: 1,
  trecho: 'O meloxicam...',
  fonte: 'Spinosa et al. (2017)',
  capitulo: '22',
);
const _fim = EventoFim(
  nivelConfianca: NivelConfianca.alta,
  modelo: 'm-1',
  thinkingLevel: 'high',
  tempos: TemposServidor(
    primeiroToken: 900,
    primeiroParagrafoValidado: 1400,
    total: 5200,
  ),
  inputTokens: 10,
  thoughtTokens: 3,
  custoUsd: 0.001,
);

RespostaSalva _salva({
  CorpoConsulta corpo = _corpo,
  EventoAlerta? alerta,
  DateTime? em,
}) => RespostaSalva(
  corpo: corpo,
  paragrafos: const [_p0],
  citacoes: const [_c1],
  alerta: alerta,
  fim: _fim,
  geradaEm: em ?? DateTime.utc(2026, 3, 12, 9),
);

void main() {
  setUpAll(() => registerFallbackValue(_corpo));

  group('chaveDaConsulta', () {
    test('é estável e distingue consultas', () {
      expect(chaveDaConsulta(_corpo), chaveDaConsulta(_corpo));
      expect(chaveDaConsulta(_corpo), isNot(chaveDaConsulta(_outro)));
      expect(chaveDaConsulta(_corpo), hasLength(16));
      const mais = CorpoConsulta(
        pergunta: 'É seguro repetir meloxicam?',
        complexidadeDica: 'baixa',
        especie: 'felino',
        pesoKg: 4.3,
        farmacos: ['meloxicam'],
      );
      expect(chaveDaConsulta(mais), isNot(chaveDaConsulta(_corpo)));
    });

    test('é o prefixo de 16 hex do SHA-256 do JSON do corpo', () {
      // Valor calculado fora do Dart (hashlib), para fixar o algoritmo.
      expect(chaveDaConsulta(_corpo), 'f91ab4659f4d1e5b');
    });

    test('pergunta de 4000 caracteres ainda cabe numa chave do hive', () {
      final longa = CorpoConsulta(
        pergunta: 'x' * 4000,
        complexidadeDica: 'baixa',
      );
      expect(chaveDaConsulta(longa).length, lessThan(255));
    });
  });

  group('RespostaCacheRepositoryImpl', () {
    late Directory dir;
    late Box<dynamic> caixa;

    setUp(() async {
      dir = Directory.systemTemp.createTempSync('respostas_test');
      Hive.init(dir.path);
      caixa = await Hive.openBox<dynamic>('respostas');
    });

    tearDown(() async {
      await Hive.close();
      dir.deleteSync(recursive: true);
    });

    test('ida e volta preserva tudo, inclusive alerta e fim', () async {
      final repo = RespostaCacheRepositoryImpl(caixa);
      final r = _salva(
        alerta: const EventoAlerta(
          severidade: SeveridadeAlerta.contraindicacao,
          texto: 'Evitar.',
          chunkIds: ['c1'],
        ),
      );
      await repo.salvar(r);
      final lida = (await repo.buscar(r.chave)).getOrElse((_) => null);
      expect(lida, r);
      expect(lida!.fim.tempos.primeiroToken, 900);
      expect(lida.citacoes.single.capitulo, '22');
      expect(lida.citacoes.single.pagina, isNull);
    });

    test('sem evidência e sem alerta também voltam iguais', () async {
      final repo = RespostaCacheRepositoryImpl(caixa);
      final r = RespostaSalva(
        corpo: _outro,
        paragrafos: const [],
        citacoes: const [],
        fim: const EventoFim(
          nivelConfianca: NivelConfianca.semEvidencia,
          modelo: 'm',
          tempos: TemposServidor(),
        ),
        geradaEm: DateTime.utc(2026),
      );
      await repo.salvar(r);
      expect((await repo.buscar(r.chave)).getOrElse((_) => null), r);
    });

    test(
      'buscar sem registro devolve null; salvar de novo substitui',
      () async {
        final repo = RespostaCacheRepositoryImpl(caixa);
        expect((await repo.buscar('nada')).getOrElse((_) => _salva()), isNull);
        await repo.salvar(_salva());
        await repo.salvar(_salva(em: DateTime.utc(2026, 4)));
        final h = (await repo.historico()).getOrElse((_) => []);
        expect(h, hasLength(1));
        expect(h.single.geradaEm, DateTime.utc(2026, 4));
      },
    );

    test(
      'histórico vem do mais novo para o mais antigo; remover apaga',
      () async {
        final repo = RespostaCacheRepositoryImpl(caixa);
        final antiga = _salva(em: DateTime.utc(2026));
        final nova = _salva(corpo: _outro, em: DateTime.utc(2026, 5));
        await repo.salvar(antiga);
        await repo.salvar(nova);
        expect((await repo.historico()).getOrElse((_) => []), [nova, antiga]);
        await repo.remover(nova.chave);
        expect((await repo.historico()).getOrElse((_) => []), [antiga]);
      },
    );

    test('dado corrompido vira FalhaCache', () async {
      await caixa.put('x', '{nao-json');
      final r = await RespostaCacheRepositoryImpl(caixa).historico();
      expect(r.getLeft().toNullable(), isA<FalhaCache>());
      await caixa.put(chaveDaConsulta(_corpo), '{"corpo": 1}');
      final b = await RespostaCacheRepositoryImpl(caixa)
          .buscar(chaveDaConsulta(_corpo));
      expect(b.getLeft().toNullable(), isA<FalhaCache>());
    });
  });

  group('RespostaCubit com cache', () {
    late _MockRealizar realizar;
    late StreamController<Either<Failure, EventoResposta>> ctl;
    late CacheEmMemoria cache;
    late TelemetriaEmMemoria telemetria;

    setUp(() {
      realizar = _MockRealizar();
      ctl = StreamController.broadcast();
      when(() => realizar(any())).thenAnswer((_) => ctl.stream);
      cache = CacheEmMemoria();
      telemetria = TelemetriaEmMemoria();
    });

    tearDown(() => ctl.close());

    RespostaCubit cubit() =>
        novoRespostaCubit(realizar, cache: cache, telemetria: telemetria);

    Future<void> concluir(RespostaCubit c) async {
      await c.iniciar(_corpo);
      ctl
        ..add(const Right(_p0))
        ..add(const Right(EventoCitacoes([_c1])))
        ..add(const Right(_fim));
      await Future<void>.delayed(Duration.zero);
    }

    test('salvar guarda a resposta e marca como salva', () async {
      final c = cubit();
      await concluir(c);
      expect(c.state.salva, isFalse);
      await c.salvar();
      expect(c.state.salva, isTrue);
      expect(cache.guardadas.keys, [chaveDaConsulta(_corpo)]);
      expect(cache.guardadas.values.single.paragrafos, [_p0]);
      await c.close();
    });

    test('salvar só vale para resposta concluída e nova', () async {
      final c = cubit();
      await c.iniciar(_corpo);
      await c.salvar();
      expect(cache.guardadas, isEmpty, reason: 'ainda transmitindo');
      await c.close();
    });

    test('sem rede, a consulta repetida sai do cache com o selo', () async {
      cache.guardadas[chaveDaConsulta(_corpo)] = _salva();
      final c = cubit();
      await c.iniciar(_corpo);
      ctl.add(const Left(FalhaRede('Sem conexão com o servidor.')));
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      expect(c.state.origemCache, isTrue);
      expect(c.state.fase, FaseResposta.concluida);
      expect(c.state.paragrafos, [_p0]);
      expect(c.state.geradaEm, DateTime.utc(2026, 3, 12, 9));
      expect(telemetria.registros.single.desfecho, DesfechoConsulta.cache);
      await c.close();
    });

    test('sem rede e sem cache: estado offline sem cache', () async {
      final c = cubit();
      await c.iniciar(_outro);
      ctl.add(const Left(FalhaRede('Sem conexão com o servidor.')));
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      expect(c.state.fase, FaseResposta.offlineSemCache);
      expect(c.state.origemCache, isFalse);
      expect(telemetria.registros.single.desfecho, DesfechoConsulta.falha);
      await c.close();
    });

    test('tempo esgotado sem cache é falha comum, não offline', () async {
      final c = cubit();
      await c.iniciar(_outro);
      ctl.add(const Left(FalhaTempo('demorou')));
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      expect(c.state.fase, FaseResposta.falha);
      await c.close();
    });

    test('erro do servidor nunca cai no cache', () async {
      cache.guardadas[chaveDaConsulta(_corpo)] = _salva();
      final c = cubit();
      await c.iniciar(_corpo);
      ctl.add(const Left(FalhaServidor('500')));
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      expect(c.state.fase, FaseResposta.falha);
      expect(c.state.origemCache, isFalse);
      await c.close();
    });

    test('exibirSalva mostra o histórico sem chamar o servidor', () async {
      final c = cubit();
      await c.exibirSalva(_salva());
      verifyNever(() => realizar(any()));
      expect(c.state.origemCache, isTrue);
      expect(c.state.fim, _fim);
      await c.close();
    });
  });

  group('RespostaPage com cache', () {
    testWidgets('selo de data permanente e sem botão Salvar', (tester) async {
      final realizar = _MockRealizar();
      final c = novoRespostaCubit(realizar);
      addTearDown(c.close);
      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider.value(
            value: c,
            child: RespostaPage(corpo: _corpo, salva: _salva()),
          ),
        ),
      );
      await tester.pump();
      expect(
        find.text('Resposta armazenada em 12/03 · pode estar desatualizada'),
        findsOneWidget,
      );
      expect(find.text('Meloxicam é um AINE.'), findsOneWidget);
      expect(find.text('Salvar'), findsNothing);
      expect(find.text('Atualizar'), findsOneWidget);
    });

    testWidgets('resposta nova mostra Salvar e vira Salva', (tester) async {
      final realizar = _MockRealizar();
      final ctl = StreamController<Either<Failure, EventoResposta>>();
      when(() => realizar(any())).thenAnswer((_) => ctl.stream);
      final cache = CacheEmMemoria();
      final c = novoRespostaCubit(realizar, cache: cache);
      addTearDown(() async {
        await c.close();
        await ctl.close();
      });
      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider.value(
            value: c,
            child: const RespostaPage(corpo: _corpo),
          ),
        ),
      );
      ctl
        ..add(const Right(_p0))
        ..add(const Right(EventoCitacoes([_c1])))
        ..add(const Right(_fim));
      await tester.pump();
      expect(find.textContaining('Resposta armazenada'), findsNothing);
      await tester.tap(find.text('Salvar'));
      await tester.pumpAndSettle();
      expect(find.text('Salva'), findsOneWidget);
      expect(cache.guardadas, hasLength(1));
    });

    testWidgets('offline sem cache mostra a mensagem e o atalho', (
      tester,
    ) async {
      final realizar = _MockRealizar();
      final ctl = StreamController<Either<Failure, EventoResposta>>();
      when(() => realizar(any())).thenAnswer((_) => ctl.stream);
      final c = novoRespostaCubit(realizar);
      addTearDown(() async {
        await c.close();
        await ctl.close();
      });
      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider.value(
            value: c,
            child: const RespostaPage(corpo: _corpo),
          ),
        ),
      );
      ctl.add(const Left(FalhaRede('Sem conexão com o servidor.')));
      await tester.pumpAndSettle();
      expect(
        find.text('Sem conexão. Esta consulta precisa da rede.'),
        findsOneWidget,
      );
      expect(find.byType(IlustracaoVetFarmaco), findsNothing);
      expect(find.text('Ver histórico'), findsOneWidget);
      expect(find.text('Tentar de novo'), findsOneWidget);
    });
  });

  group('HistoricoPage', () {
    Future<HistoricoCubit> abrir(
      WidgetTester tester,
      CacheEmMemoria cache, {
      String rede = 'wifi',
    }) async {
      final c = HistoricoCubit(
        ListarHistorico(cache),
        RemoverRespostaSalva(cache),
        RedeFalsa(rede),
      );
      addTearDown(c.close);
      await tester.pumpWidget(
        MaterialApp(
          home: BlocProvider.value(value: c, child: const HistoricoPage()),
        ),
      );
      await tester.pumpAndSettle();
      return c;
    }

    testWidgets('vazio convida à primeira consulta', (tester) async {
      await abrir(tester, CacheEmMemoria());
      expect(find.text('Nenhuma consulta salva ainda.'), findsOneWidget);
      expect(find.byType(IlustracaoVetFarmaco), findsOneWidget);
      expect(find.text('Fazer a primeira consulta'), findsOneWidget);
    });

    testWidgets('lista resumo e data; remover tira a linha', (tester) async {
      final cache = CacheEmMemoria();
      final r = _salva();
      cache.guardadas[r.chave] = r;
      final c = await abrir(tester, cache);
      expect(find.text('Meloxicam · felino · 4,2 kg'), findsOneWidget);
      expect(find.text('12/03'), findsOneWidget);
      await tester.tap(find.byTooltip('Remover'));
      await tester.pumpAndSettle();
      expect(cache.guardadas, isEmpty);
      expect(c.state.status, StatusHistorico.vazio);
      expect(find.text('Nenhuma consulta salva ainda.'), findsOneWidget);
    });

    testWidgets('deslizar para a esquerda remove', (tester) async {
      final cache = CacheEmMemoria();
      final r = _salva();
      cache.guardadas[r.chave] = r;
      await abrir(tester, cache);
      await tester.drag(find.byType(ListTile), const Offset(-600, 0));
      await tester.pumpAndSettle();
      expect(cache.guardadas, isEmpty);
    });

    testWidgets('faixa offline só aparece sem rede', (tester) async {
      final cache = CacheEmMemoria();
      final r = _salva();
      cache.guardadas[r.chave] = r;
      await abrir(tester, cache, rede: 'none');
      expect(
        find.text('⦿ offline — exibindo respostas salvas'),
        findsOneWidget,
      );
    });

    testWidgets('sem a faixa quando há rede', (tester) async {
      await abrir(tester, CacheEmMemoria());
      expect(find.textContaining('offline'), findsNothing);
    });
  });
}
