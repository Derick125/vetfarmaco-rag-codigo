import 'package:app/core/config/app_config.dart';
import 'package:app/core/di/injection.config.dart';
import 'package:app/features/ajustes/domain/repositories/ajustes_repository.dart';
import 'package:app/features/ajustes/domain/usecases/obter_condicao_campanha.dart';
import 'package:app/features/ajustes/domain/usecases/obter_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/salvar_condicao_campanha.dart';
import 'package:app/features/ajustes/domain/usecases/salvar_endereco_backend.dart';
import 'package:app/features/ajustes/domain/usecases/testar_backend.dart';
import 'package:app/features/bootstrap/data/repositories/configuracao_repository_impl.dart';
import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';
import 'package:app/features/bootstrap/domain/usecases/decidir_destino_inicial.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/consulta/domain/repositories/vocabulario_repository.dart';
import 'package:app/features/consulta/domain/sanitizador.dart';
import 'package:app/features/consulta/domain/usecases/obter_vocabulario.dart';
import 'package:app/features/historico/data/repositories/resposta_cache_repository_impl.dart';
import 'package:app/features/historico/domain/repositories/resposta_cache_repository.dart';
import 'package:app/features/historico/domain/usecases/buscar_resposta_salva.dart';
import 'package:app/features/historico/domain/usecases/listar_historico.dart';
import 'package:app/features/historico/domain/usecases/remover_resposta_salva.dart';
import 'package:app/features/historico/domain/usecases/salvar_resposta.dart';
import 'package:app/features/resposta/domain/repositories/rag_repository.dart';
import 'package:app/features/resposta/domain/usecases/realizar_consulta.dart';
import 'package:app/features/telemetria/data/repositories/telemetria_repository_impl.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';
import 'package:app/features/telemetria/domain/usecases/capturar_contexto_medicao.dart';
import 'package:app/features/telemetria/domain/usecases/exportar_telemetria.dart';
import 'package:app/features/telemetria/domain/usecases/listar_telemetria.dart';
import 'package:app/features/telemetria/domain/usecases/registrar_telemetria.dart';
import 'package:app/features/termo/domain/repositories/termo_repository.dart';
import 'package:app/features/termo/domain/usecases/aceitar_termo.dart';
import 'package:app/features/termo/domain/usecases/consultar_aceite_termo.dart';
import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import 'package:hive_ce_flutter/hive_ce_flutter.dart';
import 'package:injectable/injectable.dart';

/// Localizador de serviços (IoC) do app.
final GetIt getIt = GetIt.instance;

/// Inicializa `hive_ce` e registra as dependências geradas por `injectable`.
@InjectableInit()
Future<void> configureDependencies() async {
  await Hive.initFlutter();
  await getIt.init();
}

/// Caixas `hive_ce` abertas na inicialização (`docs/FRONTEND_SPEC.md` §7).
@module
abstract class HiveModule {
  /// Caixa que guarda a configuração local do app.
  @preResolve
  Future<Box<dynamic>> get caixaConfiguracao =>
      Hive.openBox<dynamic>(nomeCaixaConfiguracao);

  /// Caixa que guarda as medições de cada consulta (telemetria).
  @Named('telemetria')
  @preResolve
  Future<Box<dynamic>> get caixaTelemetria =>
      Hive.openBox<dynamic>(nomeCaixaTelemetria);

  /// Caixa que guarda as respostas salvas (histórico e leitura offline).
  @Named('respostas')
  @preResolve
  Future<Box<dynamic>> get caixaRespostas =>
      Hive.openBox<dynamic>(nomeCaixaRespostas);
}

/// Configuração de build (`--dart-define`).
@module
abstract class ConfigModule {
  /// Lê `API_BASE_URL` e `CLIENT_API_KEY`.
  @singleton
  AppConfig get appConfig => const AppConfig.fromEnvironment();
}

/// Cliente HTTP compartilhado.
@module
abstract class NetworkModule {
  /// `Dio` com limites de tempo; o endereço vem de cada chamada.
  @singleton
  Dio get dio => Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
    ),
  );
}

/// Provedores de casos de uso do domínio.
///
/// `domain/` não pode importar `injectable` (Regra de Dependência,
/// `ARCHITECTURE.md` §2) — o registro fica aqui, fora da camada.
@module
abstract class DomainModule {
  /// Provê o caso de uso que decide o destino inicial do app.
  @injectable
  DecidirDestinoInicial decidirDestinoInicial(ConfiguracaoRepository repo) =>
      DecidirDestinoInicial(repo);

  /// Provê o caso de uso que consulta o aceite do termo.
  @injectable
  ConsultarAceiteTermo consultarAceiteTermo(TermoRepository repo) =>
      ConsultarAceiteTermo(repo);

  /// Provê o caso de uso que registra o aceite do termo.
  @injectable
  AceitarTermo aceitarTermo(TermoRepository repo) => AceitarTermo(repo);

  /// Provê o caso de uso que lê o endereço do back-end em vigor.
  @injectable
  ObterEnderecoBackend obterEnderecoBackend(ConfiguracaoRepository repo) =>
      ObterEnderecoBackend(repo);

  /// Provê o caso de uso que testa o back-end.
  @injectable
  TestarBackend testarBackend(AjustesRepository repo) => TestarBackend(repo);

  /// Provê o caso de uso que grava o endereço do back-end.
  @injectable
  SalvarEnderecoBackend salvarEnderecoBackend(AjustesRepository repo) =>
      SalvarEnderecoBackend(repo);

  /// Provê o caso de uso que obtém o vocabulário controlado.
  @injectable
  ObterVocabulario obterVocabulario(VocabularioRepository repo) =>
      ObterVocabulario(repo);

  /// Provê o caso de uso que monta o corpo sanitizado da consulta.
  @injectable
  MontarCorpoConsulta montarCorpoConsulta(Sanitizador sanitizador) =>
      MontarCorpoConsulta(sanitizador);

  /// Provê o caso de uso que envia a consulta ao back-end.
  @injectable
  RealizarConsulta realizarConsulta(RagRepository repo) =>
      RealizarConsulta(repo);

  /// Provê o caso de uso que grava a telemetria de uma consulta.
  @injectable
  RegistrarTelemetria registrarTelemetria(TelemetriaRepository repo) =>
      RegistrarTelemetria(repo);

  /// Provê o caso de uso que lista a telemetria gravada.
  @injectable
  ListarTelemetria listarTelemetria(TelemetriaRepository repo) =>
      ListarTelemetria(repo);

  /// Provê o caso de uso que exporta a telemetria em CSV.
  @injectable
  ExportarTelemetria exportarTelemetria(
    TelemetriaRepository repo,
    CompartilhadorCsv compartilhador,
  ) => ExportarTelemetria(repo, compartilhador);

  /// Provê o caso de uso que guarda uma resposta no histórico.
  @injectable
  SalvarResposta salvarResposta(RespostaCacheRepository repo) =>
      SalvarResposta(repo);

  /// Provê o caso de uso que procura a resposta guardada de uma consulta.
  @injectable
  BuscarRespostaSalva buscarRespostaSalva(RespostaCacheRepository repo) =>
      BuscarRespostaSalva(repo);

  /// Provê o caso de uso que lista o histórico.
  @injectable
  ListarHistorico listarHistorico(RespostaCacheRepository repo) =>
      ListarHistorico(repo);

  /// Provê o caso de uso que remove uma resposta do histórico.
  @injectable
  RemoverRespostaSalva removerRespostaSalva(RespostaCacheRepository repo) =>
      RemoverRespostaSalva(repo);

  /// Provê o caso de uso que lê a condição de rede da campanha.
  @injectable
  ObterCondicaoCampanha obterCondicaoCampanha(AjustesRepository repo) =>
      ObterCondicaoCampanha(repo);

  /// Provê o caso de uso que grava a condição de rede da campanha.
  @injectable
  SalvarCondicaoCampanha salvarCondicaoCampanha(AjustesRepository repo) =>
      SalvarCondicaoCampanha(repo);

  /// Provê o caso de uso que reúne rede, condição e modelo no envio.
  @injectable
  CapturarContextoMedicao capturarContextoMedicao(
    CondicaoRede rede,
    AjustesRepository ajustes,
    ObterEnderecoBackend endereco,
  ) => CapturarContextoMedicao(rede, ajustes, endereco);
}
