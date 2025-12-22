const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"


export async function validateToken(token: string): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE_URL}/users/me`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
  
      return res.ok; 
    } catch (err) {
      console.error("Token validation failed:", err);
      return false;
    }
  }
  