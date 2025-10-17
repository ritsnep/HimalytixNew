class JournalHistory {
    constructor() {
        this.history = [];
        this.currentIndex = -1;
        this.maxHistory = 50;
    }

    pushState(state) {
        // Remove any future states if we're in the middle of history
        this.history = this.history.slice(0, this.currentIndex + 1);
        this.history.push(JSON.stringify(state));
        
        if (this.history.length > this.maxHistory) {
            this.history.shift();
        }
        
        this.currentIndex = this.history.length - 1;
    }

    undo() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            return JSON.parse(this.history[this.currentIndex]);
        }
        return null;
    }

    redo() {
        if (this.currentIndex < this.history.length - 1) {
            this.currentIndex++;
            return JSON.parse(this.history[this.currentIndex]);
        }
        return null;
    }
}