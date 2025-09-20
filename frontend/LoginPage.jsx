import { useState } from "react";

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();
    const res = await fetch("http://localhost:8000/api/auth/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();

    if (data.access) {
      localStorage.setItem("access", data.access);
      onLogin(data.user);
    } else if (data.mfa_required) {
      alert("MFA required: " + data.methods.join(", "));
    } else {
      alert("Login failed");
    }
  };

  const handleRegister = async () => {
    const res = await fetch("http://localhost:8000/api/auth/register/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (data.id) {
      alert("Registered! Please check email to verify.");
    } else {
      alert("Registration failed: " + JSON.stringify(data));
    }
  };

  return (
    <div>
      <h2>Login or Register</h2>
      <form onSubmit={handleLogin}>
        <input type="email" placeholder="Email" value={email}
          onChange={(e) => setEmail(e.target.value)} />
        <input type="password" placeholder="Password" value={password}
          onChange={(e) => setPassword(e.target.value)} />
        <button type="submit">Login</button>
      </form>
      <button onClick={handleRegister}>Register</button>
    </div>
  );
}
