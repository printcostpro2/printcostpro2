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
badge_new = "connected: [amber, 'fa-cloud', 'Firebase conectado · Sin iniciar sesión'],"
if badge_old in html:
    html = html.replace(badge_old, badge_new, 1)
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
elif auth_new not in html:
    raise SystemExit("No se encontró la función de inicio de sesión esperada; despliegue cancelado.")

TARGET.write_text(html, encoding="utf-8")
print("Estado Firebase y persistencia de sesión actualizados correctamente.")
