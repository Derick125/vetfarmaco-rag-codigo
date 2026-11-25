import 'package:app/core/di/injection.dart';
import 'package:app/core/theme/app_theme.dart';
import 'package:app/features/ajustes/presentation/cubit/ajustes_cubit.dart';
import 'package:app/features/ajustes/presentation/pages/ajustes_page.dart';
import 'package:app/features/bootstrap/presentation/cubit/bootstrap_cubit.dart';
import 'package:app/features/bootstrap/presentation/pages/abertura_page.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/consulta/presentation/cubit/consulta_cubit.dart';
import 'package:app/features/consulta/presentation/pages/consulta_page.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:app/features/historico/presentation/cubit/historico_cubit.dart';
import 'package:app/features/historico/presentation/pages/historico_page.dart';
import 'package:app/features/inicio/presentation/pages/inicio_page.dart';
import 'package:app/features/onboarding/onboarding_module.dart';
import 'package:app/features/onboarding/presentation/cubit/introducao_cubit.dart';
import 'package:app/features/onboarding/presentation/pages/introducao_page.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_cubit.dart';
import 'package:app/features/resposta/presentation/pages/resposta_page.dart';
import 'package:app/features/sobre/presentation/pages/sobre_page.dart';
import 'package:app/features/telemetria/presentation/cubit/telemetria_cubit.dart';
import 'package:app/features/telemetria/presentation/pages/telemetria_page.dart';
import 'package:app/features/termo/presentation/cubit/termo_cubit.dart';
import 'package:app/features/termo/presentation/pages/termo_page.dart';
import 'package:app/shared/widgets/pagina_animada.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await configureDependencies();
  await registrarOnboarding(getIt);
  runApp(const VetFarmacoApp());
}

final _router = GoRouter(
  routes: [
    GoRoute(
      path: '/termo',
      pageBuilder: (context, state) => paginaAnimada(
        state: state,
        child: BlocProvider(
          create: (_) => getIt<TermoCubit>(),
          child: const TermoPage(),
        ),
      ),
    ),
    GoRoute(
      path: '/inicio',
      pageBuilder: (context, state) =>
          paginaAnimada(state: state, child: const InicioPage()),
    ),
    GoRoute(
      path: '/introducao',
      pageBuilder: (context, state) => paginaAnimada(
        state: state,
        child: BlocProvider(
          create: (_) => getIt<IntroducaoCubit>(),
          child: const IntroducaoPage(),
        ),
      ),
    ),
    GoRoute(
      path: '/sobre',
      pageBuilder: (context, state) =>
          paginaAnimada(state: state, child: const SobrePage()),
    ),
    GoRoute(
      path: '/consulta',
      pageBuilder: (context, state) => paginaAnimada(
        state: state,
        child: BlocProvider(
          create: (_) => getIt<ConsultaCubit>(),
          child: const ConsultaPage(),
        ),
      ),
    ),
    GoRoute(
      path: '/consulta/:id',
      redirect: (context, state) =>
          state.extra is CorpoConsulta || state.extra is RespostaSalva
          ? null
          : '/consulta',
      pageBuilder: (context, state) {
        final extra = state.extra;
        return paginaAnimada(
          state: state,
          child: BlocProvider(
            create: (_) => getIt<RespostaCubit>(),
            child: extra is RespostaSalva
                ? RespostaPage(corpo: extra.corpo, salva: extra)
                : RespostaPage(corpo: extra! as CorpoConsulta),
          ),
        );
      },
    ),
    GoRoute(
      path: '/historico',
      pageBuilder: (context, state) => paginaAnimada(
        state: state,
        child: BlocProvider(
          create: (_) => getIt<HistoricoCubit>(),
          child: const HistoricoPage(),
        ),
      ),
    ),
    GoRoute(
      path: '/telemetria',
      pageBuilder: (context, state) => paginaAnimada(
        state: state,
        child: BlocProvider(
          create: (_) => getIt<TelemetriaCubit>(),
          child: const TelemetriaPage(),
        ),
      ),
    ),
    GoRoute(
      path: '/ajustes',
      pageBuilder: (context, state) => paginaAnimada(
        state: state,
        child: BlocProvider(
          create: (_) => getIt<AjustesCubit>(),
          child: const AjustesPage(),
        ),
      ),
    ),
    GoRoute(
      path: '/',
      builder: (context, state) => BlocProvider(
        create: (_) => getIt<BootstrapCubit>(),
        child: const AberturaPage(),
      ),
    ),
  ],
);

/// Raiz do app — PoC acadêmica, sem prescrição clínica (CLAUDE.md §1).
class VetFarmacoApp extends StatelessWidget {
  /// Cria a raiz do app.
  const new({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'VetFarmaco',
      debugShowCheckedModeBanner: false,
      theme: appTheme,
      darkTheme: temaEscuro,
      routerConfig: _router,
    );
  }
}
