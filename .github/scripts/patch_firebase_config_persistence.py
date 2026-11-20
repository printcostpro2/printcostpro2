from pathlib import Path

TARGET = Path("y/index.html")
if not TARGET.is_file():
    raise SystemExit("No se encuentra y/index.html; despliegue cancelado de forma segura.")

html = TARGET.read_text(encoding="utf-8")
marker = "/* PRINTCOST PRO: persistencia redundante de la configuración Firebase */"
already_patched = marker in html
if already_patched:
    print("La persistencia de la API ya estaba instalada; se aplicarán los ajustes de estado y sesión.")

old = '''        function loadFirebaseSettings() {
            const saved = localStorage.getItem('printcost_firebase_config');
            if (saved) {
                try {
                    const cfg = JSON.parse(saved);
                    const textarea = document.getElementById('firebase-json-input');
                    if (textarea) textarea.value = JSON.stringify(cfg, null, 2);
                    initFirebase(cfg);
                } catch(e) { console.error("Error al cargar config Firebase", e); }
            }
        }

        function saveFirebaseSettings() {
            const rawJson = document.getElementById('firebase-json-input').value.trim();
            if (!rawJson) {
                alert('Por favor, pega el bloque JSON con la configuración de tu proyecto Firebase.');
                return;
            }

            try {
                const cfg = JSON.parse(rawJson);
                if (!cfg.apiKey || !cfg.projectId) {
                    alert('El JSON introducido no contiene los campos obligatorios "apiKey" y "projectId".');
                    return;
                }

                localStorage.setItem('printcost_firebase_config', JSON.stringify(cfg));
                initFirebase(cfg);
                alert('¡Configuración de Firebase guardada y conectada correctamente!');
            } catch(e) {
                alert('El texto introducido no es un objeto JSON válido.');
            }
        }

        function clearFirebaseSettings() {
            if (confirm('¿Deseas eliminar la configuración de Firebase y volver a LocalStorage local?')) {
                localStorage.removeItem('printcost_firebase_config');
                const textarea = document.getElementById('firebase-json-input');
                if (textarea) textarea.value = '';
                
                const badge = document.getElementById('firebase-sync-badge');
                if (badge) {
                    badge.className = "bg-amber-100 text-amber-800 border border-amber-300 text-[11px] px-2.5 py-0.5 rounded-full font-bold flex items-center gap-1.5";
                    badge.innerHTML = '<i class="fa-solid fa-database"></i> LocalStorage';
                }
                alert('Firebase desconectado.');
            }
        }
'''

new = r'''        /* PRINTCOST PRO: persistencia redundante de la configuración Firebase */
        const FIREBASE_CONFIG_KEY = 'printcost_firebase_config';
        const FIREBASE_CONFIG_COOKIE = 'printcost_firebase_config_backup';
        const FIREBASE_CONFIG_DB = 'printcostpro_settings_v1';
        const FIREBASE_CONFIG_STORE = 'settings';

        function readFirebaseConfigCookie() {
            try {
                const prefix = FIREBASE_CONFIG_COOKIE + '=';
                const item = document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith(prefix));
                return item ? decodeURIComponent(item.slice(prefix.length)) : null;
            } catch (e) { return null; }
        }

        function writeFirebaseConfigCookie(raw) {
            try {
                document.cookie = FIREBASE_CONFIG_COOKIE + '=' + encodeURIComponent(raw) + '; Max-Age=31536000; Path=/; SameSite=Lax; Secure';
                return readFirebaseConfigCookie() === raw;
            } catch (e) { return false; }
        }

        function openFirebaseConfigDB() {
            return new Promise((resolve, reject) => {
                if (!window.indexedDB) { reject(new Error('IndexedDB no disponible')); return; }
                const request = indexedDB.open(FIREBASE_CONFIG_DB, 1);
                request.onupgradeneeded = () => {
                    const db = request.result;
                    if (!db.objectStoreNames.contains(FIREBASE_CONFIG_STORE)) db.createObjectStore(FIREBASE_CONFIG_STORE);
                };
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error || new Error('No se pudo abrir IndexedDB'));
                request.onblocked = () => reject(new Error('IndexedDB bloqueado'));
            });
        }

        async function writeFirebaseConfigDB(raw) {
            const db = await openFirebaseConfigDB();
            return new Promise((resolve, reject) => {
                const tx = db.transaction(FIREBASE_CONFIG_STORE, 'readwrite');
                tx.objectStore(FIREBASE_CONFIG_STORE).put(raw, FIREBASE_CONFIG_KEY);
                tx.oncomplete = () => { db.close(); resolve(true); };
                tx.onerror = () => { const e = tx.error; db.close(); reject(e || new Error('No se pudo guardar la configuración')); };
                tx.onabort = () => { const e = tx.error; db.close(); reject(e || new Error('Guardado cancelado')); };
            });
        }

        async function readFirebaseConfigDB() {
            const db = await openFirebaseConfigDB();
            return new Promise((resolve, reject) => {
                const tx = db.transaction(FIREBASE_CONFIG_STORE, 'readonly');
                const request = tx.objectStore(FIREBASE_CONFIG_STORE).get(FIREBASE_CONFIG_KEY);
                request.onsuccess = () => resolve(request.result || null);
                request.onerror = () => reject(request.error || new Error('No se pudo leer IndexedDB'));
                tx.oncomplete = () => db.close();
                tx.onerror = () => { const e = tx.error; db.close(); reject(e || new Error('Error leyendo IndexedDB')); };
            });
        }

        async function deleteFirebaseConfigDB() {
            try {
                const db = await openFirebaseConfigDB();
                await new Promise((resolve, reject) => {
                    const tx = db.transaction(FIREBASE_CONFIG_STORE, 'readwrite');
                    tx.objectStore(FIREBASE_CONFIG_STORE).delete(FIREBASE_CONFIG_KEY);
                    tx.oncomplete = resolve;
                    tx.onerror = () => reject(tx.error);
                    tx.onabort = () => reject(tx.error);
                });
                db.close();
            } catch (e) { console.warn('No se pudo borrar el respaldo IndexedDB de Firebase', e); }
        }

        async function persistFirebaseConfig(cfg) {
            const raw = JSON.stringify(cfg);
            let stored = false;
            try {
                localStorage.setItem(FIREBASE_CONFIG_KEY, raw);
                stored = localStorage.getItem(FIREBASE_CONFIG_KEY) === raw;
            } catch (e) { console.warn('LocalStorage no disponible para Firebase', e); }

            const cookieStored = writeFirebaseConfigCookie(raw);
            let indexedStored = false;
            try { indexedStored = await writeFirebaseConfigDB(raw); }
            catch (e) { console.warn('No se pudo guardar el respaldo IndexedDB de Firebase', e); }

            try {
                if (navigator.storage && navigator.storage.persist) await navigator.storage.persist();
            } catch (e) { /* La persistencia depende del navegador; se conservan los otros respaldos. */ }

            if (!stored && !cookieStored && !indexedStored) {
                throw new Error('El navegador ha bloqueado el almacenamiento permanente. Comprueba los permisos de datos del sitio.');
            }
            return raw;
        }

        async function loadFirebaseSettings() {
            let saved = null;
            try { saved = localStorage.getItem(FIREBASE_CONFIG_KEY); }
            catch (e) { console.warn('No se pudo leer LocalStorage para Firebase', e); }
            if (!saved) saved = readFirebaseConfigCookie();
            if (!saved) {
                try { saved = await readFirebaseConfigDB(); }
                catch (e) { console.warn('No se pudo recuperar el respaldo IndexedDB de Firebase', e); }
            }
            if (!saved) return;

            try {
                const cfg = JSON.parse(saved);
                if (!cfg || !cfg.apiKey || !cfg.projectId) return;
                try { localStorage.setItem(FIREBASE_CONFIG_KEY, JSON.stringify(cfg)); } catch (e) {}
                writeFirebaseConfigCookie(JSON.stringify(cfg));
                try { await writeFirebaseConfigDB(JSON.stringify(cfg)); } catch (e) {}
                const textarea = document.getElementById('firebase-json-input');
                if (textarea) textarea.value = JSON.stringify(cfg, null, 2);
                initFirebase(cfg);
            } catch (e) { console.error('Error al cargar config Firebase', e); }
        }

        async function saveFirebaseSettings() {
            const input = document.getElementById('firebase-json-input');
            const rawJson = input ? input.value.trim() : '';
            if (!rawJson) {
                alert('Por favor, pega el bloque JSON con la configuración de tu proyecto Firebase.');
                return;
            }

            try {
                const cfg = JSON.parse(rawJson);
                if (!cfg.apiKey || !cfg.projectId) {
                    alert('El JSON introducido no contiene los campos obligatorios "apiKey" y "projectId".');
                    return;
                }
                await persistFirebaseConfig(cfg);
                initFirebase(cfg);
                alert('¡Configuración de Firebase guardada y conectada correctamente!');
            } catch (e) {
                if (e instanceof SyntaxError) alert('El texto introducido no es un objeto JSON válido.');
                else alert('No se pudo guardar la configuración de forma permanente: ' + (e.message || e));
            }
        }

        function clearFirebaseSettings() {
            if (confirm('¿Deseas eliminar la configuración de Firebase y volver a LocalStorage local?')) {
                try { localStorage.removeItem(FIREBASE_CONFIG_KEY); } catch (e) {}
                document.cookie = FIREBASE_CONFIG_COOKIE + '=; Max-Age=0; Path=/; SameSite=Lax; Secure';
                deleteFirebaseConfigDB();
                const textarea = document.getElementById('firebase-json-input');
                if (textarea) textarea.value = '';

                const badge = document.getElementById('firebase-sync-badge');
                if (badge) {
                    badge.className = "bg-amber-100 text-amber-800 border border-amber-300 text-[11px] px-2.5 py-0.5 rounded-full font-bold flex items-center gap-1.5";
                    badge.innerHTML = '<i class="fa-solid fa-database"></i> LocalStorage';
                }
                alert('Firebase desconectado.');
            }
        }
'''

if not already_patched:
    if old not in html:
        raise SystemExit("No coincide el bloque de configuración Firebase esperado; se cancela el despliegue para no alterar una versión distinta.")
    html = html.replace(old, new, 1)

# Mostrar claramente que Firebase está conectado aunque aún no haya una cuenta iniciada.
badge_old = "connected: [amber, 'fa-cloud', 'Firebase: sin sesión'],"
badge_previous = "connected: [amber, 'fa-cloud', 'Firebase conectado · Sin iniciar sesión'],"
badge_new = "connected: [amber, 'fa-cloud', 'Firebase conectado · Preparando sincronización'],"
if badge_old in html:
    html = html.replace(badge_old, badge_new, 1)
elif badge_previous in html:
    html = html.replace(badge_previous, badge_new, 1)
elif badge_new not in html:
    raise SystemExit("No se encontró el indicador de estado esperado; despliegue cancelado.")

# Traducir también el nuevo texto de estado al inglés.
dict_old = '"Firebase: sin sesión": "Firebase: signed out"'
dict_new = '"Firebase conectado · Sin iniciar sesión": "Firebase connected · Not signed in"'
if dict_old in html:
    html = html.replace(dict_old, dict_new, 1)
elif dict_new not in html:
    raise SystemExit("No se encontró la traducción del indicador; despliegue cancelado.")

# Fijar expresamente la persistencia LOCAL de Firebase Authentication antes de iniciar/crear sesión.
auth_old = """        try {
            status('Conectando…');
            if (kind === 'up') await firebase.auth().createUserWithEmailAndPassword(email, pass);
            else await firebase.auth().signInWithEmailAndPassword(email, pass);"""
auth_new = """        try {
            status('Conectando…');
            try {
                const auth = firebase.auth();
                if (firebase.auth.Auth && firebase.auth.Auth.Persistence) {
                    await auth.setPersistence(firebase.auth.Auth.Persistence.LOCAL);
                }
            } catch (persistError) {
                console.warn('No se pudo fijar la persistencia local de Firebase Authentication:', persistError);
            }
            if (kind === 'up') await firebase.auth().createUserWithEmailAndPassword(email, pass);
            else await firebase.auth().signInWithEmailAndPassword(email, pass);"""
if auth_old in html:
    html = html.replace(auth_old, auth_new, 1)
elif auth_new not in html and "signInAnonymously" not in html:
    raise SystemExit("No se encontró la función de inicio de sesión esperada; despliegue cancelado.")



# PRINT COST PRO: sincronización compartida con autenticación anónima por dispositivo.
sync_start = "/* ============================================================\n   SINCRONIZACIÓN EN LA NUBE"
sync_end = "\n})();\n</script>"
start = html.find(sync_start)
if start < 0:
    raise SystemExit("No se encontró el módulo de sincronización en la nube; despliegue cancelado.")
end = html.find(sync_end, start)
if end < 0:
    raise SystemExit("No se encontró el cierre del módulo de sincronización; despliegue cancelado.")

new_sync = r'''/* ============================================================
   SINCRONIZACIÓN EN LA NUBE (Firebase Authentication anónima + Firestore)
   Cada dispositivo obtiene su propia identidad anónima automáticamente.
   Todos los dispositivos de un mismo proyecto usan printcost/shared.
   ============================================================ */
(function () {
    const KEYS = ['printcost_printers', 'printcost_quotes', 'printcost_audit_fleet', 'printcost_company_settings'];
    const META = 'printcost_cloud_meta';
    const MAX_CHARS = 900000;
    const SHARED_DOC = 'shared';
    const deviceId = (function () {
        let d = localStorage.getItem('printcost_device_id');
        if (!d) { d = 'd' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36); localStorage.setItem('printcost_device_id', d); }
        return d;
    })();
    let user = null, docRef = null, unsub = null, timer = null, lastHash = '', attached = false, busy = false;
    let authUnsub = null, authTransition = false, enabled = false, authRetryTimer = null, authRetryDelay = 1500, attachPromise = null;
    let syncRetryTimer = null, syncRetryDelay = 2000;

    const $ = id => document.getElementById(id);
    const getMeta = () => { try { return JSON.parse(localStorage.getItem(META) || '{}') || {}; } catch (e) { return {}; } };
    const setMeta = m => localStorage.setItem(META, JSON.stringify(m));
    const snap = () => { const o = {}; KEYS.forEach(k => { o[k] = localStorage.getItem(k); }); return o; };
    function hashOf(o) { const s = JSON.stringify(o); let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return h + ':' + s.length; }
    const clock = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    function status(msg, kind) {
        const el = $('cloud-sync-status'); if (!el) return;
        el.textContent = msg;
        el.className = 'text-xs font-semibold ' + ({ ok: 'text-emerald-600', err: 'text-rose-600', warn: 'text-amber-600' }[kind] || 'text-slate-500');
    }
    function badge(state, detail) {
        const b = $('firebase-sync-badge'); if (!b) return;
        const amber = 'bg-amber-100 text-amber-800 border border-amber-300', green = 'bg-emerald-100 text-emerald-800 border border-emerald-300', red = 'bg-rose-100 text-rose-800 border border-rose-300';
        const base = ' text-[11px] px-2.5 py-0.5 rounded-full font-bold flex items-center gap-1.5';
        const map = {
            local: [amber, 'fa-database', 'LocalStorage'],
            connected: [amber, 'fa-cloud', 'Firebase conectado · Preparando sincronización'],
            synced: [green, 'fa-cloud-arrow-up', 'Sincronizado'],
            error: [red, 'fa-triangle-exclamation', 'Error de sincronización']
        }[state];
        b.className = map[0] + base;
        b.title = detail || map[2];
        b.setAttribute('aria-label', detail ? 'Error de sincronización: ' + detail : map[2]);
        const visibleLabel = state === 'error' && detail ? ('Error: ' + String(detail).slice(0, 54)) : map[2];
        b.innerHTML = '<i class="fa-solid ' + map[1] + '"></i> ' + visibleLabel;
    }
    function friendly(e) {
        const c = (e && e.code) || '';
        if (c === 'auth/operation-not-allowed') return 'activa el acceso Anónimo en Firebase Authentication';
        if (c === 'auth/unauthorized-domain') return 'añade el dominio de la app en Firebase Authentication > Dominios autorizados';
        if (c === 'auth/network-request-failed') return 'sin conexión de red con Firebase';
        if (c === 'permission-denied' || c === 'firestore/permission-denied') return 'Firestore deniega el acceso: revisa las reglas del documento printcost/shared';
        if (c === 'unavailable' || c === 'firestore/unavailable' || c === 'deadline-exceeded') return 'Firebase no responde temporalmente; se volverá a intentar';
        if (c === 'failed-precondition') return 'Firestore no está listo o necesita configuración en Firebase Console';
        const message = (e && e.message) || String(e);
        return c ? c + ': ' + message : message;
    }

    function stop() {
        if (unsub) { try { unsub(); } catch (e) {} unsub = null; }
        if (timer) { clearInterval(timer); timer = null; }
    }

    function scheduleSyncRetry(error) {
        if (!enabled || !user || !docRef || syncRetryTimer) return;
        const detail = friendly(error);
        status('Conexión temporalmente interrumpida (' + detail + '). Reintentando automáticamente…', 'warn');
        syncRetryTimer = setTimeout(function () {
            syncRetryTimer = null;
            if (enabled && user && docRef) begin();
        }, syncRetryDelay);
        syncRetryDelay = Math.min(syncRetryDelay * 2, 30000);
    }

    function applyRemote(d) {
        let cur;
        try { cur = JSON.parse(d.payload); } catch (e) { status('Los datos de la nube no son válidos.', 'err'); return; }
        const importedCatalogVersion = d.clearAll ? null : localStorage.getItem('printcost_bsd_nov_2026_catalog_v1');
        if (d.clearAll) localStorage.removeItem('printcost_bsd_nov_2026_catalog_v1');
        if (importedCatalogVersion === '2026-11-v1') {
            let remotePrinters = [];
            try { remotePrinters = JSON.parse(cur['printcost_printers'] || '[]'); } catch (e) { remotePrinters = []; }
            const remoteHasBSDCatalog = Array.isArray(remotePrinters) && remotePrinters.some(p =>
                p && (p.sourceTariff === 'Tarifa BSD Noviembre 2026' || String(p.id || '').startsWith('bsd2026-'))
            );
            if (!remoteHasBSDCatalog) cur['printcost_printers'] = JSON.stringify(defaultPrinters.map(normalizePrinter));
        }
        KEYS.forEach(k => { if (cur[k] === null || cur[k] === undefined) localStorage.removeItem(k); else localStorage.setItem(k, cur[k]); });
        if (importedCatalogVersion === '2026-11-v1') localStorage.setItem('printcost_bsd_nov_2026_catalog_v1', '2026-11-v1');
        try {
            quotes = [];
            loadLocalPrinters(); loadLocalQuotes(); loadAuditFleet(); renderDashboard();
            if (typeof navigateTo === 'function') navigateTo(currentView, false);
        } catch (e) { console.error(e); }
        lastHash = hashOf(snap());
        setMeta({ uid: 'shared', lastTs: d.updatedAt || Date.now(), hash: lastHash });
        status('Datos actualizados desde la nube a las ' + clock(), 'ok'); badge('synced');
    }

    async function push(force) {
        if (!docRef || busy) return;
        const cur = snap(), h = hashOf(cur);
        if (!force && h === lastHash) return;
        const payload = JSON.stringify(cur);
        if (payload.length > MAX_CHARS) { status('Los datos superan el límite de sincronización (1 MB).', 'err'); badge('error', 'los datos superan el límite de sincronización'); return; }
        busy = true;
        try {
            const ts = Date.now();
            await docRef.set({ payload: payload, updatedAt: ts, deviceId: deviceId, v: 2 });
            lastHash = h; setMeta({ uid: 'shared', lastTs: ts, hash: h });
            status('Sincronizado a las ' + clock(), 'ok'); badge('synced');
        } catch (e) { status('Error al sincronizar: ' + friendly(e), 'err'); badge('error', friendly(e)); }
        finally { busy = false; }
    }

    async function begin() {
        stop();
        if (syncRetryTimer) { clearTimeout(syncRetryTimer); syncRetryTimer = null; }
        if (!docRef || !user) return;
        status('Sincronizando…');
        try {
            const s = await docRef.get(), m = getMeta();
            lastHash = m.uid === 'shared' ? (m.hash || '') : '';
            if (s.exists) {
                const d = s.data();
                if (m.uid !== 'shared') {
                    const useCloud = confirm('Ya hay datos compartidos en Firebase. Aceptar = cargarlos en este dispositivo (sustituye los datos locales). Cancelar = subir los datos locales de este dispositivo al espacio compartido.');
                    if (useCloud) applyRemote(d); else await push(true);
                } else if ((d.updatedAt || 0) > (m.lastTs || 0) && d.deviceId !== deviceId) {
                    if (hashOf(snap()) !== lastHash) {
                        const useCloud = confirm('Hay cambios en la nube y también datos locales distintos. Aceptar = cargar los datos compartidos. Cancelar = publicar los datos locales.');
                        if (useCloud) applyRemote(d); else await push(true);
                    } else applyRemote(d);
                } else {
                    await push(false);
                    if (!busy && hashOf(snap()) === lastHash) { status('Sincronizado a las ' + clock(), 'ok'); badge('synced'); }
                }
            } else {
                await push(true);
            }
        } catch (e) {
            status('Error al conectar con los datos compartidos: ' + friendly(e), 'err');
            badge('error', friendly(e));
            scheduleSyncRetry(e);
            return;
        }
        syncRetryDelay = 2000;
        unsub = docRef.onSnapshot(function (s) {
            if (!s.exists || (s.metadata && s.metadata.hasPendingWrites)) return;
            const d = s.data(), m = getMeta();
            if (d.deviceId === deviceId || (d.updatedAt || 0) <= (m.lastTs || 0)) return;
            applyRemote(d);
        }, function (e) {
            const detail = friendly(e);
            status('Error de conexión con Firestore: ' + detail, 'err');
            badge('error', detail);
            scheduleSyncRetry(e);
        });
        timer = setInterval(function () { push(false); }, 3000);
    }

    async function onUser(u) {
        if (!enabled) return;
        if (!u) {
            stop(); user = null; docRef = null;
            if (authTransition) return;
            authTransition = true;
            try {
                const auth = firebase.auth();
                if (firebase.auth.Auth && firebase.auth.Auth.Persistence) {
                    try { await auth.setPersistence(firebase.auth.Auth.Persistence.LOCAL); }
                    catch (persistenceError) { console.warn('Firebase no admite persistencia LOCAL en este navegador; se usará la persistencia predeterminada.', persistenceError); }
                }
                await auth.signInAnonymously();
                authRetryDelay = 1500;
            } catch (e) {
                status('No se pudo autorizar este dispositivo: ' + friendly(e), 'err'); badge('error', friendly(e));
                const code = (e && e.code) || '';
                if (!['auth/operation-not-allowed', 'auth/invalid-api-key', 'auth/app-deleted'].includes(code)) {
                    scheduleAuthRetry();
                }
            } finally { authTransition = false; }
            return;
        }

        // Migración conservadora: si había una sesión antigua con email, copia su documento
        // al documento compartido solo si este todavía no existe. Nunca sobrescribe el común.
        if (!u.isAnonymous) {
            if (authTransition) return;
            authTransition = true;
            try {
                status('Preparando los datos existentes para la sincronización compartida…');
                const db = firebase.firestore();
                const legacyRef = db.collection('printcost').doc(u.uid);
                const sharedRef = db.collection('printcost').doc(SHARED_DOC);
                const legacy = await legacyRef.get();
                const shared = await sharedRef.get();
                if (legacy.exists && !shared.exists) {
                    await sharedRef.set(legacy.data());
                    try {
                        const legacyPayload = JSON.parse(legacy.data().payload || '{}');
                        const localHash = hashOf(snap());
                        if (hashOf(legacyPayload) === localHash) {
                            setMeta({ uid: 'shared', lastTs: legacy.data().updatedAt || Date.now(), hash: localHash });
                        }
                    } catch (migrationMetaError) {
                        console.warn('No se pudo comparar el estado local durante la migración:', migrationMetaError);
                    }
                }
                await firebase.auth().signOut();
                await firebase.auth().signInAnonymously();
            } catch (e) {
                status('No se pudo preparar la sesión anterior: ' + friendly(e), 'err'); badge('error', friendly(e));
            } finally { authTransition = false; }
            return;
        }

        stop(); user = u;
        const lbl = $('cloud-sync-account');
        if (lbl) lbl.textContent = 'Este dispositivo está autorizado automáticamente.';
        docRef = firebase.firestore().collection('printcost').doc(SHARED_DOC);
        begin();
    }

    function scheduleAuthRetry() {
        if (!enabled || authRetryTimer) return;
        authRetryTimer = setTimeout(function () {
            authRetryTimer = null;
            if (!enabled) return;
            const auth = firebase.auth();
            if (auth.currentUser) onUser(auth.currentUser);
            else onUser(null);
        }, authRetryDelay);
        authRetryDelay = Math.min(authRetryDelay * 2, 30000);
    }

    async function attach() {
        if (!window.firebase || !firebase.apps || !firebase.apps.length || attached) return attachPromise;
        attached = true; enabled = true;
        attachPromise = (async function () {
            try {
                const auth = firebase.auth();
                if (firebase.auth.Auth && firebase.auth.Auth.Persistence) {
                    try { await auth.setPersistence(firebase.auth.Auth.Persistence.LOCAL); }
                    catch (persistenceError) { console.warn('No se pudo fijar persistencia LOCAL; se usará la configuración predeterminada.', persistenceError); }
                }
                authUnsub = auth.onAuthStateChanged(onUser, function (e) {
                    status('Error de autenticación Firebase: ' + friendly(e), 'err');
                    badge('error', friendly(e));
                    scheduleAuthRetry();
                });
            } catch (e) {
                status('No se pudo restaurar la sesión Firebase: ' + friendly(e), 'err');
                badge('error', friendly(e));
                scheduleAuthRetry();
            }
        })();
        return attachPromise;
    }

    function detach() {
        enabled = false; stop(); user = null; docRef = null;
        if (authRetryTimer) { clearTimeout(authRetryTimer); authRetryTimer = null; }
        if (syncRetryTimer) { clearTimeout(syncRetryTimer); syncRetryTimer = null; }
        attachPromise = null;
        if (authUnsub) { try { authUnsub(); } catch (e) {} authUnsub = null; }
        attached = false;
        if (window.firebase && firebase.apps && firebase.apps.length) {
            try { firebase.auth().signOut(); } catch (e) {}
        }
        const lbl = $('cloud-sync-account'); if (lbl) lbl.textContent = '';
        status('Firebase desconectado. Los datos locales permanecen en este dispositivo.');
    }

    window.cloudSyncNow = async function () {
        if (!user || !docRef) { status('Esperando la autorización automática de este dispositivo…', 'warn'); return; }
        await begin();
    };
    async function clearAll() {
        const cfgSaved = !!localStorage.getItem('printcost_firebase_config');
        if (cfgSaved && (!docRef || !user)) {
            throw new Error('Firebase está configurado pero todavía no está conectado. Espera a que se sincronice y vuelve a intentarlo para borrar también la copia en la nube.');
        }
        KEYS.forEach(k => localStorage.removeItem(k));
        localStorage.removeItem('printcost_bsd_nov_2026_catalog_v1');
        const empty = {}; KEYS.forEach(k => { empty[k] = null; });
        if (docRef && user) {
            const ts = Date.now();
            await docRef.set({ payload: JSON.stringify(empty), updatedAt: ts, deviceId: deviceId, v: 2, clearAll: true });
            lastHash = hashOf(snap());
            setMeta({ uid: 'shared', lastTs: ts, hash: lastHash });
            status('Base de datos vaciada en este dispositivo y en los demás dispositivos conectados.', 'ok');
            badge('synced');
        } else {
            lastHash = hashOf(snap());
            localStorage.removeItem(META);
            status('Datos locales vaciados. No hay una conexión Firebase activa.', 'ok');
            badge('local');
        }
        try {
            if (typeof quotes !== 'undefined') quotes = [];
            if (typeof loadLocalPrinters === 'function') loadLocalPrinters();
            if (typeof loadLocalQuotes === 'function') loadLocalQuotes();
            if (typeof loadAuditFleet === 'function') loadAuditFleet();
            if (typeof renderDashboard === 'function') renderDashboard();
            if (typeof navigateTo === 'function') navigateTo(currentView, false);
        } catch (e) { console.warn('No se pudo actualizar la pantalla tras vaciar la base de datos:', e); }
        return true;
    }

    window.clearPrintCostDatabase = async function () {
        if (!confirm('¿Estás seguro de que quieres vaciar la base de datos? Se eliminarán los catálogos, presupuestos, auditorías y ajustes de empresa.')) return false;
        if (!confirm('SEGUNDA CONFIRMACIÓN: esta acción no se puede deshacer y también borrará los datos compartidos en Firebase para todos tus dispositivos. ¿Confirmas el vaciado?')) return false;
        try {
            await clearAll();
            alert('La base de datos se ha vaciado correctamente.');
            return true;
        } catch (e) {
            alert('No se ha podido vaciar la base de datos: ' + (e.message || e));
            return false;
        }
    };
    window.__cloudSync = { attach: attach, detach: detach, push: push, snap: snap, clearAll: clearAll };

    const _init = window.initFirebase;
    window.initFirebase = function () { _init.apply(this, arguments); attach(); };
    const _clear = window.clearFirebaseSettings;
    window.clearFirebaseSettings = function () {
        _clear.apply(this, arguments);
        detach();
    };
})();'''

html = html[:start] + new_sync + html[end + len("\n})();"):]

old_ui = r'''                    <p class="text-xs text-slate-500">Después de conectar Firebase, inicia sesión (o crea una cuenta) con tu email y contraseña. Usa la misma cuenta en cada dispositivo y tu catálogo, presupuestos y auditorías se mantendrán sincronizados.</p>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block font-semibold text-slate-700 text-xs mb-1">Email de la cuenta</label>
                            <input type="email" id="cloud-email" autocomplete="username" class="w-full text-xs border border-slate-300 rounded-lg p-2">
                        </div>
                        <div>
                            <label class="block font-semibold text-slate-700 text-xs mb-1">Contraseña</label>
                            <input type="password" id="cloud-password" autocomplete="current-password" class="w-full text-xs border border-slate-300 rounded-lg p-2">
                        </div>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
                        <button onclick="cloudSignIn()" class="bg-brand-600 hover:bg-brand-700 text-white font-bold px-4 py-2.5 rounded-lg text-xs shadow flex items-center gap-2"><i class="fa-solid fa-right-to-bracket"></i> Iniciar sesión</button>
                        <button onclick="cloudSignUp()" class="bg-slate-800 hover:bg-slate-700 text-white font-bold px-4 py-2.5 rounded-lg text-xs shadow flex items-center gap-2"><i class="fa-solid fa-user-plus"></i> Crear cuenta</button>
                        <button onclick="cloudSyncNow()" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-4 py-2.5 rounded-lg text-xs shadow flex items-center gap-2"><i class="fa-solid fa-rotate"></i> Sincronizar ahora</button>
                        <button onclick="cloudSignOut()" class="bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold px-3 py-2.5 rounded-lg text-xs">Cerrar sesión</button>
                    </div>
                    <p id="cloud-sync-account" class="text-xs font-semibold text-slate-700"></p>
                    <p id="cloud-sync-status" class="text-xs font-semibold text-slate-500">Aún no has iniciado sesión.</p>

                    <details class="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg p-3">
                        <summary class="cursor-pointer font-semibold text-slate-700">Cómo configurar tu proyecto de Firebase</summary>
                        <ol class="list-decimal pl-5 mt-2 space-y-1.5">
                            <li>Crea un proyecto en console.firebase.google.com y añade una app web para obtener el bloque JSON de configuración.</li>
                            <li>En Authentication, activa el método «Correo electrónico/contraseña».</li>
                            <li>En Firestore Database, crea la base de datos y pega estas reglas de seguridad:</li>
                        </ol>
                        <pre class="mt-2 bg-slate-900 text-slate-100 rounded-lg p-3 overflow-x-auto text-[11px] leading-relaxed">rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /printcost/{uid} {
      allow read, write: if request.auth != null
                         && request.auth.uid == uid;
    }
  }
}</pre>
                        <p class="mt-2">Pega el JSON en este panel, pulsa «Guardar y Conectar Firebase» e inicia sesión.</p>
                    </details>'''
new_ui = r'''                    <p class="text-xs text-slate-500">No necesitas crear una cuenta ni compartir contraseñas. Cada dispositivo se autoriza automáticamente y todos sincronizan los mismos datos del proyecto Firebase.</p>
                    <div class="flex flex-wrap items-center gap-2">
                        <button onclick="cloudSyncNow()" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-4 py-2.5 rounded-lg text-xs shadow flex items-center gap-2"><i class="fa-solid fa-rotate"></i> Sincronizar ahora</button>
                    </div>
                    <p id="cloud-sync-account" class="text-xs font-semibold text-slate-700"></p>
                    <p id="cloud-sync-status" class="text-xs font-semibold text-slate-500">Esperando la autorización automática de este dispositivo…</p>

                    <details class="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg p-3">
                        <summary class="cursor-pointer font-semibold text-slate-700">Cómo configurar tu proyecto de Firebase</summary>
                        <ol class="list-decimal pl-5 mt-2 space-y-1.5">
                            <li>Crea un proyecto en console.firebase.google.com y añade una app web para obtener el bloque JSON de configuración.</li>
                            <li>En Authentication &gt; Método de acceso, activa «Anónimo».</li>
                            <li>En Firestore Database, crea la base de datos y sustituye las reglas por estas:</li>
                        </ol>
                        <pre class="mt-2 bg-slate-900 text-slate-100 rounded-lg p-3 overflow-x-auto text-[11px] leading-relaxed">rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /printcost/{documentId} {
      allow read, write: if request.auth != null
        && (
          (documentId == 'shared')
          ||
          (documentId != 'shared'
            && request.auth.uid == documentId
            && request.auth.token.firebase.sign_in_provider == 'password')
        );
    }
  }
}</pre>
                        <p class="mt-2">Pega el JSON en este panel y pulsa «Guardar y Conectar Firebase». La aplicación autorizará este dispositivo automáticamente.</p>
                        <p class="mt-2 text-amber-700 font-semibold">Importante: cualquier sesión autenticada en este proyecto puede acceder al documento compartido. Para reforzar la protección, configura también Firebase App Check.</p>
                    </details>'''
if old_ui in html:
    html = html.replace(old_ui, new_ui, 1)
elif "No necesitas crear una cuenta ni compartir contraseñas." not in html:
    raise SystemExit("No se encontró el panel de sincronización esperado; despliegue cancelado.")
html = html.replace(
    "Importante: las reglas permiten el acceso anónimo al documento compartido de este proyecto. No compartas la configuración de tu Firebase con personas ajenas a tus dispositivos.",
    "Importante: cualquier sesión autenticada en este proyecto puede acceder al documento compartido. Para reforzar la protección, configura también Firebase App Check."
)

# Actualizar las traducciones del panel al inglés.
replacements = {
    '"Sincronizar mis datos entre dispositivos": "Sync my data across devices"': '"Sincronizar mis datos entre dispositivos": "Sync my data across devices"',
    '"Después de conectar Firebase, inicia sesión (o crea una cuenta) con tu email y contraseña. Usa la misma cuenta en cada dispositivo y tu catálogo, presupuestos y auditorías se mantendrán sincronizados.": "After connecting Firebase, sign in (or create an account) with your email and password. Use the same account on every device and your catalog, quotes and audits will stay in sync."': '"No necesitas crear una cuenta ni compartir contraseñas. Cada dispositivo se autoriza automáticamente y todos sincronizan los mismos datos del proyecto Firebase.": "You do not need to create an account or share passwords. Each device is authorized automatically and all devices sync the same Firebase project data."',
    '"Email de la cuenta": "Account email", ': '',
    '"Contraseña": "Password", ': '',
    '"Iniciar sesión": "Sign in", ': '',
    '"Crear cuenta": "Create account", ': '',
    '"Cerrar sesión": "Sign out", ': '',
    '"Aún no has iniciado sesión.": "You are not signed in yet."': '"Esperando la autorización automática de este dispositivo…": "Waiting for this device to be authorized automatically…"',
    '"En Authentication, activa el método «Correo electrónico/contraseña».": "In Authentication, enable the \\"Email/Password\\" sign-in method."': '"En Authentication > Método de acceso, activa «Anónimo».": "In Authentication > Sign-in method, enable \\"Anonymous\\"."',
    '"En Firestore Database, crea la base de datos y pega estas reglas de seguridad:": "In Firestore Database, create the database and paste these security rules:"': '"En Firestore Database, crea la base de datos y sustituye las reglas por estas:": "In Firestore Database, create the database and replace the rules with these:"',
    '"Pega el JSON en este panel, pulsa «Guardar y Conectar Firebase» e inicia sesión.": "Paste the JSON in this panel, click \\"Save and Connect Firebase\\" and sign in."': '"Pega el JSON en este panel y pulsa «Guardar y Conectar Firebase». La aplicación autorizará este dispositivo automáticamente.": "Paste the JSON in this panel and click \\"Save and Connect Firebase\\". The app will authorize this device automatically."',
    '"Firebase: sin sesión": "Firebase: signed out"': '"Firebase conectado · Preparando sincronización": "Firebase connected · Preparing sync"',
    '"Conectado a Firebase. Inicia sesión para sincronizar.": "Connected to Firebase. Sign in to sync."': '"Esperando la autorización automática de este dispositivo…": "Waiting for this device to be authorized automatically…"',
    '"Conectando…": "Connecting…", ': '',
    '"Sesión cerrada. Los datos siguen guardados en este dispositivo.": "Signed out. Your data remains saved on this device.", ': '',
    '"Email o contraseña incorrectos.": "Incorrect email or password.", ': '',
    '"Ese email ya tiene cuenta. Inicia sesión.": "This email already has an account. Sign in.", ': '',
    '"La contraseña debe tener al menos 6 caracteres.": "The password must be at least 6 characters.", ': '',
    '"Activa el método «Correo electrónico/contraseña» en Firebase Authentication.": "Enable the \\"Email/Password\\" method in Firebase Authentication.", ': '',
    '"Email no válido.": "Invalid email.", ': '',
    '"Introduce tu email y contraseña.": "Enter your email and password.", ': '',
    '"Inicia sesión primero.": "Sign in first.", ': '',
    '"Primero guarda y conecta la configuración de Firebase.": "First save and connect your Firebase configuration.", ': '',
};
for a, b in replacements.items():
    if a in html:
        html = html.replace(a, b)
# Remove obsolete login helpers from translations, if still present.
html = html.replace('"Sincronizado": "Synced",', '"Sincronizado": "Synced",');
if "signInAnonymously" not in html or "doc(SHARED_DOC)" not in html or "documentId == 'shared'" not in html:
    raise SystemExit("La nueva sincronización anónima compartida no superó las comprobaciones; despliegue cancelado.")




# PRINT COST PRO: dejar visible únicamente el panel de configuración JSON de Firebase.
# Se ejecuta en el navegador porque el HTML principal se recupera desde Firebase Hosting
# durante cada despliegue y la interfaz de ajustes forma parte de ese documento.
cleanup_marker = 'id="printcost-minimal-firebase-settings-ui"'
cleanup_script = r'''<script id="printcost-minimal-firebase-settings-ui">
(function () {
    const syncTitle = 'Sincronizar mis datos entre dispositivos';
    const backupTitle = 'Copia de Seguridad e Importación';
    const excludedKeys = new Set([
        'printcost_firebase_config',
        'printcost_firebase_config_backup',
        'printcost_cloud_meta',
        'printcost_device_id'
    ]);
    let scheduled = false;

    function cleanText(value) {
        return String(value || '').replace(/\s+/g, ' ').trim();
    }

    function findTitle(title) {
        const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]'));
        return headings.find(el => cleanText(el.textContent) === title) || null;
    }

    function findCard(heading, expectedText) {
        let node = heading && heading.parentElement;
        for (let depth = 0; node && node !== document.body && depth < 12; depth++, node = node.parentElement) {
            const text = cleanText(node.textContent);
            if (text.includes(expectedText) && !text.includes('Configuración API de Firebase (JSON Completo)')) {
                const classes = typeof node.className === 'string' ? node.className : '';
                if (/(?:^|\s)rounded-(?:lg|xl|2xl)(?:\s|$)/.test(classes) ||
                    (node.matches && node.matches('section,article'))) return node;
            }
        }
        return heading ? heading.parentElement : null;
    }

    function hideSyncPanel() {
        const heading = findTitle(syncTitle);
        if (!heading) return;
        const panel = findCard(heading, syncTitle);
        if (panel && !panel.querySelector('#firebase-json-input')) {
            panel.style.display = 'none';
            panel.setAttribute('aria-hidden', 'true');
        }
    }

    function downloadJson(filename, payload) {
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
    }

    function makeFullBackup() {
        const data = {};
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith('printcost_') && !excludedKeys.has(key)) {
                data[key] = localStorage.getItem(key);
            }
        }
        downloadJson('printcostpro-copia-seguridad-' + new Date().toISOString().slice(0, 10) + '.json', {
            app: 'PrintCost Pro',
            type: 'printcostpro-full-backup',
            version: 1,
            createdAt: new Date().toISOString(),
            data: data
        });
        alert('Copia de seguridad completa creada correctamente.');
    }

    async function restoreFullBackup(file) {
        try {
            const raw = await file.text();
            const backup = JSON.parse(raw);
            if (!backup || backup.app !== 'PrintCost Pro' ||
                backup.type !== 'printcostpro-full-backup' ||
                !backup.data || typeof backup.data !== 'object' || Array.isArray(backup.data)) {
                throw new Error('El archivo no es una copia de seguridad completa de PrintCost Pro.');
            }
            if (!confirm('Restaurar esta copia sustituirá los datos actuales de este dispositivo. ¿Deseas continuar?')) return;
            Object.keys(backup.data).forEach(function (key) {
                if (key.startsWith('printcost_') && !excludedKeys.has(key) && typeof backup.data[key] === 'string') {
                    localStorage.setItem(key, backup.data[key]);
                }
            });
            if (window.__cloudSync && window.__cloudSync.push) await window.__cloudSync.push(true);
            alert('Copia de seguridad restaurada correctamente. Se actualizará la aplicación.');
            location.reload();
        } catch (e) {
            alert('No se pudo restaurar la copia de seguridad: ' + (e.message || e));
        }
    }

    function findVaciarButton() {
        return Array.from(document.querySelectorAll('button')).find(function (button) {
            return /^(Vaciar Datos|Vaciar base de datos)$/i.test(cleanText(button.textContent));
        }) || null;
    }

    function setupBackupPanel() {
        const heading = findTitle(backupTitle);
        if (!heading) return;
        const panel = findCard(heading, backupTitle) || heading.parentElement;
        if (!panel) return;

        let tools = panel.querySelector('#printcost-full-backup-tools');
        if (!tools) {
            tools = document.createElement('div');
            tools.id = 'printcost-full-backup-tools';
            tools.className = 'mt-3 mb-4 rounded-xl border border-slate-200 bg-slate-50 p-3';
            tools.innerHTML = '<p class="font-bold text-slate-800 mb-1">Copia de seguridad completa</p>' +
                '<p class="text-xs text-slate-600 mb-3">Guarda catálogos, presupuestos, auditorías y ajustes de empresa en un archivo JSON. La configuración y la sesión de Firebase no se incluyen.</p>' +
                '<div class="flex flex-wrap items-center gap-2">' +
                '<button type="button" id="printcost-create-full-backup" class="bg-brand-600 hover:bg-brand-700 text-white font-bold px-4 py-2 rounded-lg text-xs">Hacer copia de seguridad</button>' +
                '<label for="printcost-restore-full-backup" class="bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 font-bold px-4 py-2 rounded-lg text-xs cursor-pointer">Restaurar copia de seguridad</label>' +
                '<input type="file" id="printcost-restore-full-backup" accept=".json,application/json" class="hidden">' +
                '</div>';
            heading.insertAdjacentElement('afterend', tools);
            tools.querySelector('#printcost-create-full-backup').addEventListener('click', makeFullBackup);
            tools.querySelector('#printcost-restore-full-backup').addEventListener('change', function (event) {
                const file = event.target.files && event.target.files[0];
                if (file) restoreFullBackup(file);
                event.target.value = '';
            });
        }

        const vaciar = findVaciarButton();
        if (vaciar && !vaciar.dataset.printcostDoubleConfirm) {
            vaciar.dataset.printcostDoubleConfirm = '1';
            vaciar.textContent = 'Vaciar base de datos';
            vaciar.setAttribute('onclick', 'return window.clearPrintCostDatabase()');
            vaciar.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopImmediatePropagation();
                window.clearPrintCostDatabase();
            }, true);
        }
    }

    function update() {
        hideSyncPanel();
        setupBackupPanel();
    }

    function schedule() {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(function () {
            scheduled = false;
            update();
        });
    }

    update();
    if (document.documentElement) {
        const observer = new MutationObserver(schedule);
        observer.observe(document.documentElement, { childList: true, subtree: true });
    }
})();
</script>'''
cleanup_script = cleanup_script.strip()
if cleanup_marker in html:
    script_tag = '<script id="printcost-minimal-firebase-settings-ui">'
    script_start = html.find(script_tag)
    script_end = html.find('</script>', script_start)
    if script_start < 0 or script_end < 0:
        raise SystemExit("El script de ajustes anterior está incompleto; despliegue cancelado.")
    html = html[:script_start] + cleanup_script + html[script_end + len('</script>'):]
else:
    html += '\n' + cleanup_script + '\n'

# PRINT COST PRO: restaurar automáticamente la configuración guardada al abrir.
firebase_bootstrap = r'''<script id="printcost-firebase-config-autorestore">
(function () {
    if (window.__printcostFirebaseAutoRestoreInstalled) return;
    window.__printcostFirebaseAutoRestoreInstalled = true;
    let started = false;
    let fieldRestoreRunning = false;

    async function restoreSavedConfigInField() {
        if (fieldRestoreRunning) return;
        const input = document.getElementById('firebase-json-input');
        if (!input || input.value.trim()) return;
        fieldRestoreRunning = true;
        try {
            let raw = null;
            try { raw = localStorage.getItem('printcost_firebase_config'); } catch (e) {}
            if (!raw) {
                try {
                    const cookie = document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith('printcost_firebase_config_backup='));
                    if (cookie) raw = decodeURIComponent(cookie.slice('printcost_firebase_config_backup='.length));
                } catch (e) {}
            }
            if (!raw && window.indexedDB) {
                try {
                    const request = indexedDB.open('printcostpro_settings_v1', 1);
                    raw = await new Promise((resolve, reject) => {
                        request.onsuccess = () => {
                            const db = request.result;
                            const tx = db.transaction('settings', 'readonly');
                            const get = tx.objectStore('settings').get('printcost_firebase_config');
                            get.onsuccess = () => { const value = get.result || null; db.close(); resolve(value); };
                            get.onerror = () => { const error = get.error; db.close(); reject(error); };
                        };
                        request.onerror = () => reject(request.error);
                    });
                } catch (e) {}
            }
            if (raw && input.isConnected && !input.value.trim()) {
                const cfg = JSON.parse(raw);
                if (cfg && cfg.apiKey && cfg.projectId) input.value = JSON.stringify(cfg, null, 2);
            }
        } catch (e) { console.warn('No se pudo rellenar el campo con la configuración Firebase guardada:', e); }
        finally { fieldRestoreRunning = false; }
    }

    async function restoreWhenReady() {
        if (started) return;
        started = true;
        try {
            for (let attempt = 0; attempt < 60; attempt++) {
                if (window.firebase && firebase.apps &&
                    typeof window.loadFirebaseSettings === 'function' &&
                    typeof window.initFirebase === 'function') break;
                await new Promise(resolve => setTimeout(resolve, 250));
            }
            if (!window.firebase || !firebase.apps ||
                typeof window.loadFirebaseSettings !== 'function' ||
                typeof window.initFirebase !== 'function') {
                throw new Error('No se pudo cargar el módulo Firebase. Recarga la aplicación.');
            }

            if (firebase.apps.length) {
                if (window.__cloudSync && typeof window.__cloudSync.attach === 'function') {
                    await window.__cloudSync.attach();
                }
                return;
            }

            let hasSavedConfig = false;
            try { hasSavedConfig = !!localStorage.getItem('printcost_firebase_config'); } catch (e) {}
            try { hasSavedConfig = hasSavedConfig || document.cookie.includes('printcost_firebase_config_backup='); } catch (e) {}
            if (!hasSavedConfig) {
                try {
                    const request = indexedDB.open('printcostpro_settings_v1', 1);
                    hasSavedConfig = await new Promise((resolve, reject) => {
                        request.onupgradeneeded = () => {
                            const db = request.result;
                            if (!db.objectStoreNames.contains('settings')) db.createObjectStore('settings');
                        };
                        request.onsuccess = () => {
                            const db = request.result;
                            const tx = db.transaction('settings', 'readonly');
                            const get = tx.objectStore('settings').get('printcost_firebase_config');
                            get.onsuccess = () => { const value = !!get.result; db.close(); resolve(value); };
                            get.onerror = () => { const error = get.error; db.close(); reject(error); };
                        };
                        request.onerror = () => reject(request.error);
                    });
                } catch (e) {}
            }
            if (!hasSavedConfig) return;

            await window.loadFirebaseSettings();
            if (window.__cloudSync && typeof window.__cloudSync.attach === 'function' &&
                firebase.apps && firebase.apps.length) {
                await window.__cloudSync.attach();
            }
        } catch (e) {
            console.error('No se pudo restaurar la configuración Firebase guardada:', e);
            const status = document.getElementById('cloud-sync-status');
            if (status) status.textContent = 'La configuración sigue guardada, pero no se pudo iniciar Firebase: ' + (e.message || e);
        }
    }

    function launch() {
        setTimeout(restoreWhenReady, 300);
        setTimeout(restoreSavedConfigInField, 500);
        if (document.documentElement) {
            const observer = new MutationObserver(function () { restoreSavedConfigInField(); });
            observer.observe(document.documentElement, { childList: true, subtree: true });
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', launch, { once: true });
    } else launch();
    window.addEventListener('pageshow', function () {
        if (window.firebase && firebase.apps && firebase.apps.length && window.__cloudSync) {
            window.__cloudSync.attach();
        }
    });
})();
</script>'''
if 'id="printcost-firebase-config-autorestore"' not in html:
    html += '\n' + firebase_bootstrap + '\n'


TARGET.write_text(html, encoding="utf-8")
print("Estado Firebase y persistencia de sesión actualizados correctamente.")
