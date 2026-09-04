import { createContext, useContext, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "./api";
import { LanguageSwitch, useI18n } from "./i18n";
import type { StaffUser } from "./types";

export type AuthStatus = {
  required: boolean;
  logged_in: boolean;
  setup_needed: boolean;
  shop_name: string;
  user: StaffUser | null;
};

type AuthValue = {
  user: StaffUser | null;
  shopName: string;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthGate");
  return ctx;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [auth, setAuth] = useState<AuthStatus | null>(null);

  async function refresh() {
    const next = await api<AuthStatus>("/api/operator/status");
    setAuth(next);
  }

  async function logout() {
    await api("/api/operator/logout", { method: "POST" });
    await refresh();
  }

  useEffect(() => {
    refresh().catch(() =>
      setAuth({
        required: true,
        logged_in: false,
        setup_needed: false,
        shop_name: t("shopNameFallback"),
        user: null,
      }),
    );
  }, [t]);

  useEffect(() => {
    function onLost() {
      setAuth((cur) => (cur ? { ...cur, logged_in: false, user: null } : cur));
    }
    window.addEventListener("im-auth-lost", onLost);
    return () => window.removeEventListener("im-auth-lost", onLost);
  }, []);

  if (!auth) {
    return <p className="muted" style={{ padding: 24 }}>{t("loading")}</p>;
  }

  const value: AuthValue = {
    user: auth.user,
    shopName: auth.shop_name || t("shopNameFallback"),
    refresh,
    logout,
  };

  if (auth.setup_needed && !auth.logged_in) {
    return (
      <AuthContext.Provider value={value}>
        <SetupForm shopName={auth.shop_name} onDone={refresh} />
      </AuthContext.Provider>
    );
  }

  if (!auth.logged_in) {
    return (
      <AuthContext.Provider value={value}>
        <LoginForm shopName={auth.shop_name} onDone={refresh} />
      </AuthContext.Provider>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function LoginForm({ shopName, onDone }: { shopName: string; onDone: () => Promise<void> }) {
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/operator/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      await onDone();
    } catch {
      setError(t("loginWrong"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <form className="card form-grid auth-card" onSubmit={submit}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="auth-brand">
            <span className="mark">{(shopName || t("shopNameFallback")).trim().charAt(0).toUpperCase()}</span>
            <div>
              <div className="brand">{shopName || t("shopNameFallback")}</div>
              <h2>{t("loginRequired")}</h2>
            </div>
          </div>
          <LanguageSwitch />
        </div>
        <p className="muted">{t("loginHint")}</p>
        {error && <div className="banner">{error}</div>}
        <label>
          {t("username")}
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus />
        </label>
        <label>
          {t("password")}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <button className="btn" type="submit" disabled={busy || !username.trim() || password.length < 4}>
          {t("login")}
        </button>
        <p className="muted">{t("demoLoginHint")}</p>
      </form>
    </div>
  );
}

function SetupForm({ shopName, onDone }: { shopName: string; onDone: () => Promise<void> }) {
  const { t } = useI18n();
  const [username, setUsername] = useState("admin");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/operator/setup", {
        method: "POST",
        body: JSON.stringify({ username, password, display_name: displayName }),
      });
      await onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("couldNotCreate"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <form className="card form-grid auth-card" onSubmit={submit}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="auth-brand">
            <span className="mark">{(shopName || t("shopNameFallback")).trim().charAt(0).toUpperCase()}</span>
            <div>
              <div className="brand">{shopName || t("shopNameFallback")}</div>
              <h2>{t("setupAdmin")}</h2>
            </div>
          </div>
          <LanguageSwitch />
        </div>
        <p className="muted">{t("setupHint")}</p>
        {error && <div className="banner">{error}</div>}
        <label>
          {t("username")}
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          {t("displayName")}
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </label>
        <label>
          {t("password")}
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </label>
        <button className="btn" type="submit" disabled={busy || username.trim().length < 2 || password.length < 4}>
          {t("create")}
        </button>
      </form>
    </div>
  );
}

export function UserAdmin() {
  const { t } = useI18n();
  const { user: me, logout } = useAuth();
  const [users, setUsers] = useState<StaffUser[]>([]);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [isAgent, setIsAgent] = useState(true);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [pwById, setPwById] = useState<Record<number, string>>({});

  async function load() {
    setUsers(await api<StaffUser[]>("/api/users"));
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : t("updateFailed")));
  }, [t]);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNote("");
    try {
      await api("/api/users", {
        method: "POST",
        body: JSON.stringify({
          username,
          password,
          display_name: displayName,
          is_sales_agent: isAgent,
        }),
      });
      setUsername("");
      setDisplayName("");
      setPassword("");
      setNote(t("userSaved"));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("couldNotCreate"));
    }
  }

  async function save(user: StaffUser, patch: Partial<StaffUser> & { password?: string }) {
    setError("");
    setNote("");
    try {
      await api(`/api/users/${user.id}`, { method: "PATCH", body: JSON.stringify(patch) });
      setNote(t("userSaved"));
      setPwById((cur) => ({ ...cur, [user.id]: "" }));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("updateFailed"));
    }
  }

  return (
    <div className="card form-grid">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>{t("staffAccounts")}</h3>
        <button className="btn ghost" type="button" onClick={() => logout()}>
          {t("logout")}
        </button>
      </div>
      <p className="muted">
        {t("staffAccountsHint")}
        {me ? ` ${t("loggedInAs", { name: me.display_name || me.username })}` : ""}
      </p>
      {error && <div className="banner">{error}</div>}
      {note ? <p className="muted">{note}</p> : null}
      {users.map((u) => (
        <div key={u.id} className="staff-row">
          <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div>
              <b>{u.display_name}</b>
              <div className="sku">{u.username}</div>
            </div>
            <label className="row" style={{ gap: 8 }}>
              <input
                type="checkbox"
                checked={u.is_sales_agent}
                onChange={(e) => save(u, { is_sales_agent: e.target.checked })}
              />
              {t("isSalesAgent")}
            </label>
            <label className="row" style={{ gap: 8 }}>
              <input
                type="checkbox"
                checked={u.is_active}
                onChange={(e) => save(u, { is_active: e.target.checked })}
              />
              {t("userActive")}
            </label>
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <input
              type="password"
              value={pwById[u.id] || ""}
              onChange={(e) => setPwById((cur) => ({ ...cur, [u.id]: e.target.value }))}
              placeholder={t("newPassword")}
              autoComplete="new-password"
            />
            <button
              className="btn ghost"
              type="button"
              disabled={(pwById[u.id] || "").length < 4}
              onClick={() => save(u, { password: pwById[u.id] })}
            >
              {t("save")}
            </button>
          </div>
        </div>
      ))}
      <form className="form-grid" onSubmit={add}>
        <h3 style={{ margin: 0 }}>{t("addUser")}</h3>
        <label>
          {t("username")}
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" />
        </label>
        <label>
          {t("displayName")}
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </label>
        <label>
          {t("password")}
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </label>
        <label className="row" style={{ gap: 8 }}>
          <input type="checkbox" checked={isAgent} onChange={(e) => setIsAgent(e.target.checked)} />
          {t("isSalesAgent")}
        </label>
        <button className="btn" type="submit" disabled={username.trim().length < 2 || password.length < 4}>
          {t("addUser")}
        </button>
      </form>
    </div>
  );
}
