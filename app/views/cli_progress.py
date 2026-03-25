class CLIProgressView:
    def final_stretch(self, collected: int, target: int, subreddit: str | None = None) -> None:
        if subreddit:
            print(f"Final Stretch: {collected}/{target} posts collected (Source: r/{subreddit})")
        else:
            print(f"Final Stretch: {collected}/{target} posts collected")

