import { useState } from "react";
import LoginPage from "./LoginPage";
import ResendVerification from "./components/ResendVerification";

function App() {
  const [user, setUser] = useState(null);

  const handleLogout = () => {
    localStorage.removeItem("access");
    setUser(null);
  };

  return (
    <div style={{ padding: 20, fontFamily: "Arial" }}>
      <h1>Django Auth Template Demo</h1>
      {!user ? (
        <>
          <LoginPage onLogin={setUser} />
          <hr />
          <ResendVerification />   {/* 👈 added here */}
        </>
      ) : (
        <div>
          <h2>Welcome, {user.email}</h2>
          <button onClick={handleLogout}>Logout</button>
        </div>
      )}
    </div>
  );
}

export default App;
