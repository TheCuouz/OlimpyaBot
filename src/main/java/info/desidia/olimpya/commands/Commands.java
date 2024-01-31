package info.desidia.olimpya.commands;

import net.dv8tion.jda.api.hooks.ListenerAdapter;



public class Commands extends ListenerAdapter {

	public static void main (String[] args) {
		if (args.length < 1) {
			System.out.println("You have to provide a token as first argument!");
			System.exit(1);
		}
	}
}