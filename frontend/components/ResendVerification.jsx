import React, { useState } from "react";

const ResendVerification = () => {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const handleResend = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch("http://127.0.0.1:8000/api/auth/resend-verification/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (response.ok) {
        setMessage("✅ Verification email resent! Check your inbox.");
      } else {
        const data = await response.json();
        setMessage(`❌ Error: ${data.detail || "Could not resend email"}`);
      }
    } catch (error) {
      setMessage("❌ Network error, please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "20px auto", textAlign: "center" }}>
      <h2>Resend Verification Email</h2>
      <form onSubmit={handleResend}>
        <input
          type="email"
          placeholder="Enter your email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{ width: "100%", padding: 8, marginBottom: 10 }}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Sending..." : "Resend"}
        </button>
      </form>
      {message && <p>{message}</p>}
    </div>
  );
};

export default ResendVerification;
