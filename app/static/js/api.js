const API = {
  async getPermutations(username, max_permutations = 25, enable_digit_collisions = false) {
    const resp = await fetch('/api/permutations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, max_permutations, enable_digit_collisions })
    });
    return resp.json();
  },

  async getDossiers() {
    const resp = await fetch('/api/history');
    return resp.json();
  },

  async getDossier(id) {
    const resp = await fetch(`/api/dossiers/${id}`);
    return resp.json();
  }
};