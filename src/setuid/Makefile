.PHONY := build clean

bash:
	@cp /bin/bash /usr/local/bin/sbash
	@sudo chown root /usr/local/bin/sbash
	@sudo chmod u+s,+x /usr/local/bin/sbash

clean:
	@sudo rm -f geteuid seteuid /usr/local/bin/sbash

build: clean bash
	@cc geteuid.c -o geteuid
	@chmod +x geteuid
	@cc seteuid.c -o seteuid
	@sudo chown root seteuid
	@sudo chmod u+s,+x seteuid

test: build
	@./demo.sh
