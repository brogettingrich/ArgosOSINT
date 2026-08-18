const API = {
  async getPermutations(username, max_permutations = 25) {
    const resp = await fetch('/api/permutations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, max_permutations })
    });
    return resp.json();
  },

  async getDossiers() {
    const resp = await fetch('/api/dossiers');
    return resp.json();
  },

  async getDossier(id) {
    const resp = await fetch(`/api/dossiers/${id}`);
    return resp.json();
  }
};